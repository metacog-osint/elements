"""Source health: is each feed answering, and how old is its newest data?

    python doctrine/kit/tic.py health doctrine/sources.json --out doctrine/health.json

A source counts as healthy only when it answers and its data are fresh. A source
that fails or goes stale turns its layers grey (no data) instead of looking quiet.
States follow Watchfloor's feed health: fresh, late, stale, failing, never, up
(answering, but no timestamp to judge freshness).
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

UA = "TheIntelligenceCompany-health/0.1 (+https://theintelligence.company)"
MAX_BYTES = 2_000_000
STATES = ("fresh", "late", "stale", "failing", "never", "up")

_RSS_DATE = re.compile(rb"<(?:pubDate|updated|published|dc:date|lastBuildDate)>([^<]{8,40})</", re.I)


def _parse_time(raw: str) -> datetime | None:
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _json_path(obj, path: str):
    for part in path.split("."):
        if isinstance(obj, list):
            obj = obj[int(part)] if part.lstrip("-").isdigit() else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        if obj is None:
            return None
    return obj


def latest_time(body: bytes, headers, probe: dict) -> datetime | None:
    """Newest data time from a JSON path, the newest feed date, or Last-Modified."""
    kind = probe.get("expect", "any")
    if kind == "json" and probe.get("time_path"):
        try:
            v = _json_path(json.loads(body), probe["time_path"])
            if isinstance(v, (int, float)):
                return datetime.fromtimestamp(v / (1000 if v > 1e11 else 1), timezone.utc)
            if isinstance(v, str):
                return _parse_time(v)
        except (ValueError, IndexError):
            return None
    if kind == "feed":
        times = [t for t in (_parse_time(m.decode("utf-8", "replace")) for m in _RSS_DATE.findall(body)) if t]
        if times:
            return max(times)
    lm = headers.get("Last-Modified")
    return _parse_time(lm) if lm else None


def probe_one(src: dict, now: datetime, timeout: float = 20.0) -> dict:
    probe = src.get("probe")
    if not probe or not probe.get("url"):
        return {"state": "never", "note": "no probe defined"}
    req = urllib.request.Request(probe["url"], headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(MAX_BYTES)
            status, headers = r.status, r.headers
    except urllib.error.HTTPError as e:
        return {"state": "failing", "http": e.code, "error": f"HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"state": "failing", "error": type(e).__name__ + ": " + str(getattr(e, "reason", e))[:120]}
    if not body.strip():
        return {"state": "failing", "http": status, "error": "empty body"}
    t = latest_time(body, headers, probe)
    out = {"http": status, "bytes": len(body)}
    cadence = src.get("cadence_s")
    if t is None or not cadence:
        out["state"] = "up"
        if t:
            out["latest"] = t.strftime("%Y-%m-%dT%H:%M:%SZ")
        return out
    age = (now - t).total_seconds()
    out.update(latest=t.strftime("%Y-%m-%dT%H:%M:%SZ"), age_s=int(age))
    out["state"] = "fresh" if age <= cadence else "late" if age <= 2 * cadence else "stale"
    return out


def sources_with_probes(register: dict) -> list[dict]:
    """Sources from a doctrine/sources.json: a full list, or 'extra' rows beside a native register."""
    if register.get("sources"):
        return register["sources"]
    return [{"id": k, **v} for k, v in (register.get("extra") or {}).items()]


def run(register_path: Path, out_path: Path | None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    register = json.loads(register_path.read_text(encoding="utf-8"))
    prev = {}
    if out_path and out_path.exists():
        prev = json.loads(out_path.read_text(encoding="utf-8")).get("sources", {})
    result = {}
    for src in sources_with_probes(register):
        if src.get("use") == "excluded":
            continue
        r = probe_one(src, now)
        last_ok = prev.get(src["id"], {}).get("last_ok")
        if r["state"] in ("fresh", "late", "up"):
            last_ok = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        r["last_ok"] = last_ok
        result[src["id"]] = r
    report = {
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule": "A failing or stale source turns its layers grey (no data); it never reads as quiet.",
        "summary": {s: sum(1 for r in result.values() if r["state"] == s) for s in STATES},
        "sources": result,
    }
    if out_path:
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tic health")
    ap.add_argument("register", help="doctrine/sources.json")
    ap.add_argument("--out", help="write the health report here (keeps last_ok across runs)")
    a = ap.parse_args(argv)
    rep = run(Path(a.register), Path(a.out) if a.out else None)
    for sid, r in rep["sources"].items():
        print(f"  {r['state']:8} {sid}  {r.get('latest', '')} {r.get('error', '')}".rstrip())
    print("Summary:", ", ".join(f"{k} {v}" for k, v in rep["summary"].items() if v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
