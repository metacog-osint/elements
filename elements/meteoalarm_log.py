"""Archive of MeteoAlarm yellow warnings (retention fix E1, 18 Nov 2026).

Orange and red warnings are feed items, so the history log keeps them. Yellow ones are only a count per country in
the feed, and data/meteoalarm.json is not committed, so each yellow warning vanished when it expired. This file keeps
them: one line per warning the first time it is seen and again whenever the warning changes (a new message in its
chain, a new expiry or level), appended to history/meteoalarm/YYYY-MM-DD.jsonl for the UTC day of the run. A day's
file is gzipped once the day is over (YYYY-MM-DD.jsonl.gz) and never written again. history/meteoalarm/state.json
holds the fingerprint of each yellow warning still in force, so a warning in force for days is logged once, not on
every run.

Source: MeteoAlarm (EUMETNET), CC BY 4.0 as stated on feeds.meteoalarm.org: reuse is allowed with attribution, so
each line carries the national service's name (`sender`) and its LICENSE string (`credit`), and history/README.md
credits MeteoAlarm and EUMETNET. Polygons are left out (size); `points` and `precision` say where it was placed."""
import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

FORMAT = "elements-meteoalarm-yellow/1"
YELLOW = 2
KEYS = ("id", "identifier", "feed", "country", "sender", "event", "headline", "level", "colour", "type_code", "type",
        "severity", "urgency", "certainty", "sent", "onset", "expires", "web", "credit", "areas", "placed",
        "precision", "points")


def _path(root: Path, day: str, closed: bool = False) -> Path:
    return Path(root) / (f"{day}.jsonl.gz" if closed else f"{day}.jsonl")


def fingerprint(rec: dict) -> str:
    """What makes a message a different one: its identifier and sent time, and what a later update can move."""
    key = json.dumps([rec.get("identifier"), rec.get("sent"), rec.get("level"), rec.get("expires"), rec.get("onset"),
                      rec.get("headline"), rec.get("areas")], ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def load_state(root: Path) -> dict:
    p = Path(root) / "state.json"
    if p.exists():
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(s.get("open"), dict):
                return s
        except ValueError:
            pass
    return {"format": FORMAT, "open": {}}


def save_state(root: Path, state: dict) -> None:
    """One warning per line, sorted by id, so a run's commit touches only the lines that changed."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rows = [f"{json.dumps(k)}:{json.dumps(v, separators=(',', ':'))}" for k, v in sorted(state["open"].items())]
    text = json.dumps({"format": FORMAT}, separators=(",", ":"))[:-1] + ',"open":{\n' + ",\n".join(rows) + "\n}}\n"
    (root / "state.json").write_text(text, encoding="utf-8", newline="\n")


def update(root: Path, records, now: datetime) -> list:
    """Append the new and changed yellow warnings in `records` (data/meteoalarm.json's records) to today's file, drop
    expired ones from the state, and gzip finished days. Returns the lines written."""
    root = Path(root)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    day = stamp[:10]
    state = load_state(root)
    open_ = state["open"]
    lines = []
    for rec in sorted(records or [], key=lambda r: r.get("id") or ""):
        if rec.get("level") != YELLOW or not rec.get("id") or (rec.get("expires") or "") <= stamp:
            continue
        fp = fingerprint(rec)
        prev = open_.get(rec["id"])
        if prev and prev[0] == fp:
            continue
        line = {"format": FORMAT, "at": stamp, "change": "changed" if prev else "new"}
        line.update({k: rec.get(k) for k in KEYS})
        lines.append(line)
        open_[rec["id"]] = [fp, rec.get("expires")]
    for k in [k for k, v in open_.items() if (v[1] or "") <= stamp]:
        del open_[k]
    if lines:
        # A closed day is never reopened: if today's file was already gzipped (a clock set back), write beside it.
        p = _path(root, day) if not _path(root, day, True).exists() else root / f"{day}.late.jsonl"
        root.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as fh:
            for x in lines:
                fh.write(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n")
    close_days(root, day)
    save_state(root, state)
    return lines


def close_days(root: Path, today: str) -> list:
    """Gzip every plain day file before today, once, byte for byte the same on any machine. Never overwrites a .gz."""
    done = []
    for p in sorted(Path(root).glob("*.jsonl")):
        day = p.name[:10]
        if day >= today:
            continue
        gz = Path(root) / (p.name + ".gz")
        if gz.exists():   # a finished day is never rewritten: keep both rather than replace
            continue
        with open(gz, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as fh:
            fh.write(p.read_bytes())
        p.unlink()
        done.append(day)
    return done


def read_all(root: Path) -> list:
    out = []
    for p in sorted(Path(root).glob("*.jsonl*")):
        op = gzip.open if p.suffix == ".gz" else open
        with op(p, "rt", encoding="utf-8") as fh:
            out += [json.loads(x) for x in fh if x.strip()]
    return out
