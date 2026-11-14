"""Elements' history: every item it has published, kept after it leaves the feed. Standard library only.

The feed carries what is active now; this keeps what was. Each run compares the feed just built with the items open
after the last run and writes one line per change to history/log/YYYY/MM/DD.jsonl:

- new      an item appears (the first time, or again after it ended)
- changed  its tier or response_stage changed (an alert level moved); other edits only bump `updates`
- ended    it left the feed while its source was read successfully this run, so a failed fetch never ends anything;
           or, for an NWS alert issued and ended between two runs (found by the catch-up query), new and ended at once.
           ended_at is the item's own valid_until when that falls between its last sighting and this run, otherwise
           this run's time (the true end lies between last_seen and ended_at)

Every line carries the full contract-v2 item as it stood (the last version, for ended), so the log alone rebuilds the
picture at any past time. Closed days are gzipped once and never rewritten. history/state.json holds the items open
now. site/data/ended.geojson lists the items that ended in the last ENDED_DAYS days: not drawn on the map and not in
the feed, for readers such as COP's outage triage that ask what happened in a window, not what is active.

The line format is meant for the doctrine kit to adopt for every program unchanged (`program` and `lane` say whose)."""
import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FORMAT = "tic-history/1"
ENDED_DAYS = 7
RECENT_DAYS = 4                                    # ids ended this recently are not logged again by the catch-up
STATUS_KEYS = ("tier", "response_stage")           # a change here is a "changed" line
VOLATILE = ("published_at",)                       # a change only here is no change at all


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _t(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def lane(feature: dict) -> str | None:
    """The source lane an item comes from: its first source's id, which is the lane's key in data/health.json."""
    src = (feature.get("properties") or {}).get("sources") or []
    return (src[0] or {}).get("id") if src else None


def fingerprint(feature: dict) -> str:
    """A hash of the item without the fields that change on every run (published_at, each source's accessed_at)."""
    p = dict(feature.get("properties") or {})
    for k in VOLATILE:
        p.pop(k, None)
    p["sources"] = [{k: v for k, v in (s or {}).items() if k != "accessed_at"} for s in p.get("sources") or []]
    text = json.dumps({"geometry": feature.get("geometry"), "properties": p}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


TIER_RANK = {"routine": 0, "anomaly": 1, "warning": 2}


def _line(at, change, entry, item, **extra):
    p = item.get("properties") or {}
    return {"format": FORMAT, "at": at, "change": change, "id": p.get("id"), "program": p.get("program"),
            "lane": entry["lane"], "first_seen": entry["first_seen"], "last_seen": entry["last_seen"],
            "peak_tier": entry["peak_tier"], "updates": entry["updates"], **extra, "item": item}


def lanes_ok(health: dict) -> set:
    """Lanes read successfully on the run that wrote this health record (its last success is its last check)."""
    return {k for k, v in (health or {}).items()
            if isinstance(v, dict) and v.get("last_ok") and v.get("last_ok") == v.get("checked_at")}


def update(state: dict, feed: dict, health: dict, now: datetime, caught: list | None = None) -> tuple[dict, list]:
    """(new state, log lines) after one run. state: {"open": {id: entry}}; feed: the FeatureCollection just built;
    health: data/health.json of this run; caught: items for NWS alerts issued since the last run and no longer
    active (built like feed items). Pure: no files read or written."""
    at = _stamp(now)
    open_ = dict((state or {}).get("open") or {})
    keep_from = _stamp(now - timedelta(days=RECENT_DAYS))
    recent = {k: v for k, v in ((state or {}).get("recently_ended") or {}).items() if v >= keep_from}
    lines = []
    ok = lanes_ok(health)
    dropped = {x.get("id") for x in feed.get("dropped") or []}
    seen = set()
    for f in feed.get("features") or []:
        p = f.get("properties") or {}
        iid = p.get("id")
        if not iid or iid in seen:
            continue
        seen.add(iid)
        fp = fingerprint(f)
        e = open_.get(iid)
        if e is None:
            e = {"lane": lane(f), "first_seen": at, "last_seen": at, "hash": fp, "updates": 0,
                 "peak_tier": p.get("tier"), "status": [p.get(k) for k in STATUS_KEYS], "item": f}
            open_[iid] = e
            lines.append(_line(at, "new", e, f))
            continue
        status = [p.get(k) for k in STATUS_KEYS]
        moved = status != e.get("status")
        e.update({"last_seen": at, "item": f})
        if fp != e.get("hash"):
            e["hash"] = fp
            e["updates"] = e.get("updates", 0) + 1
        if TIER_RANK.get(p.get("tier"), 0) > TIER_RANK.get(e.get("peak_tier"), 0):
            e["peak_tier"] = p.get("tier")
        if moved:
            lines.append(_line(at, "changed", e, f, was=dict(zip(STATUS_KEYS, e.get("status") or [None, None]))))
            e["status"] = status
    for iid in sorted(set(open_) - seen):
        e = open_[iid]
        if iid in dropped or e.get("lane") not in ok:
            continue           # its source failed this run, or the linter held it back: not ended
        lines.append(_line(at, "ended", e, e["item"], ended_at=end_time(e, now), end_reason="left the feed"))
        recent[iid] = at
        del open_[iid]
    for f in caught or []:
        p = f.get("properties") or {}
        iid = p.get("id")
        if not iid or iid in open_ or iid in seen or iid in recent:
            continue           # live now, or already ended (seen live, or caught on an earlier run)
        until = _t(p.get("valid_until"))
        end = _stamp(min(until, now)) if until else at
        e = {"lane": lane(f), "first_seen": p.get("data_as_of") or at, "last_seen": None, "hash": fingerprint(f),
             "updates": 0, "peak_tier": p.get("tier")}
        lines.append(_line(at, "new", e, f, seen_live=False))
        lines.append(_line(at, "ended", e, f, ended_at=end, end_reason="issued and ended between runs", seen_live=False))
        recent[iid] = at
    return {"format": FORMAT, "updated_at": at, "recently_ended": dict(sorted(recent.items())), "open": open_}, lines


def end_time(entry: dict, now: datetime) -> str:
    """When an item that left the feed ended, as well as the runs show it: its own valid_until when that falls between
    its last sighting and this run (a warning that ran out), otherwise this run (ended early, cancelled, or no end
    time given: the true end lies between last_seen and now)."""
    until = _t(((entry.get("item") or {}).get("properties") or {}).get("valid_until"))
    last = _t(entry.get("last_seen"))
    return _stamp(until) if until and last and last <= until <= now else _stamp(now)


def ended_ids_in(lines: list) -> set:
    return {x["id"] for x in lines if x.get("change") == "ended"}


# --- files ---------------------------------------------------------------------------------------------------------

def log_path(root: Path, day: str, closed: bool = False) -> Path:
    y, m, d = day.split("-")
    return root / "log" / y / m / (f"{d}.jsonl.gz" if closed else f"{d}.jsonl")


def load_state(root: Path) -> dict:
    p = root / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"format": FORMAT, "open": {}}


def save_state(root: Path, state: dict) -> None:
    """One open item per line, sorted by id, so a run's commit touches only the lines that changed."""
    root.mkdir(parents=True, exist_ok=True)
    rows = [f"{json.dumps(k, ensure_ascii=False)}:{json.dumps(v, ensure_ascii=False, separators=(',', ':'), sort_keys=True)}"
            for k, v in sorted((state.get("open") or {}).items())]
    head = {k: v for k, v in state.items() if k != "open"}
    text = (json.dumps(head, ensure_ascii=False, separators=(",", ":"))[:-1] + ',"open":{\n' + ",\n".join(rows)
            + "\n}}\n")
    (root / "state.json").write_text(text, encoding="utf-8", newline="\n")


def append_log(root: Path, lines: list) -> None:
    """Append each line to its own day's file (the day of its `at`). A closed day is never reopened: a late line for
    a closed day goes to the open file of the day it is written."""
    by_day = {}
    for x in lines:
        by_day.setdefault(x["at"][:10], []).append(x)
    for day, rows in sorted(by_day.items()):
        p = log_path(root, day)
        if log_path(root, day, closed=True).exists():
            p = log_path(root, rows[-1]["at"][:10])
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as fh:
            for x in rows:
                fh.write(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n")


def close_days(root: Path, today: str) -> list:
    """Gzip every plain day file before today (written once, byte for byte the same on any machine)."""
    done = []
    for p in sorted((root / "log").glob("*/*/*.jsonl")):
        day = f"{p.parent.parent.name}-{p.parent.name}-{p.name[:2]}"
        if day >= today:
            continue
        gz = p.with_suffix(".jsonl.gz")
        data = p.read_bytes()
        with open(gz, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as fh:
            fh.write(data)
        p.unlink()
        done.append(day)
    return done


def read_days(root: Path, first: str, last: str) -> list:
    """Every log line from day `first` to day `last` (YYYY-MM-DD, inclusive), oldest first."""
    out = []
    d, end = datetime.fromisoformat(first), datetime.fromisoformat(last)
    while d <= end:
        day = d.strftime("%Y-%m-%d")
        for p, opener in ((log_path(root, day, True), gzip.open), (log_path(root, day), open)):
            if p.exists():
                with opener(p, "rt", encoding="utf-8") as fh:
                    out += [json.loads(s) for s in fh if s.strip()]
        d += timedelta(days=1)
    return out


def ended_collection(root: Path, state: dict, now: datetime, days: int = ENDED_DAYS) -> dict:
    """Items that ended in the last `days` days and are not open again, newest end first. Each feature is the item as
    it last stood, with a `history` member (not in properties, so the item stays contract-valid)."""
    since = now - timedelta(days=days)
    lines = read_days(root, (since - timedelta(days=1)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    open_ids = set((state.get("open") or {}).keys())
    last = {}
    for x in lines:
        if x.get("change") == "ended" and (_t(x.get("ended_at")) or since) >= since and x["id"] not in open_ids:
            last[x["id"]] = x                   # the latest end wins when an item ended twice
    feats = []
    for x in sorted(last.values(), key=lambda x: x.get("ended_at") or "", reverse=True):
        f = dict(x["item"])
        f["history"] = {k: x.get(k) for k in ("first_seen", "last_seen", "ended_at", "end_reason", "peak_tier", "updates",
                                              "seen_live") if x.get(k) is not None}
        feats.append(f)
    return {"type": "FeatureCollection", "format": FORMAT, "program": "elements", "generated_at": _stamp(now),
            "window_days": days,
            "what": ("Elements items that ended in the last %d days: they left the feed while their source was read "
                     "successfully, or were NWS alerts issued and ended between two runs. Not active: not drawn on the "
                     "map and not in the feed. Each keeps its last version; `history` gives first_seen, last_seen, "
                     "ended_at (the first run without it, or the alert's own end) and end_reason. The full record is "
                     "history/log/ in the Elements repository." % days),
            "features": feats}
