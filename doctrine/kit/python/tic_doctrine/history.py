"""History: every item a program has published, kept after it leaves the feed. Standard library only.

    python doctrine/kit/tic.py history site/data/feed.geojson --dir history [--health data/health.json]
                                       [--ended site/data/ended.geojson] [--days 7]

A feed carries what is active now; this keeps what was. Each run compares the feed just built with the items open
after the last run and writes one line per change to <dir>/log/YYYY/MM/DD.jsonl (format tic-history/1):

- new      an item appears (the first time, or again after it ended)
- changed  its tier or response_stage changed (an alert level moved); other edits only bump `updates`. With
           --reading-key (opt-in, 0.5.13), also when that property moved: a program whose item ids stay the same
           from one reading of a series to the next (Headwind: data_as_of) logs each new reading
- ended    it left the feed while its source was read successfully this run, so a failed fetch never ends anything;
           or, for an item issued and ended between two runs (found by a program's own catch-up query), new and ended
           at once. ended_at is the item's own valid_until when that falls between its last sighting and this run,
           otherwise this run's time (the true end lies between last_seen and ended_at)

Every line carries the full contract-v2 item as it stood (the last version, for ended), so the log alone rebuilds the
picture at any past time. Closed days are gzipped once and never rewritten. <dir>/state.json holds the items open
now. ended_collection() lists the items that ended in the last ENDED_DAYS days: a file a program serves beside its
feed (data/ended.geojson), not drawn on the map and not in the feed, for readers such as COP's outage triage that ask
what happened in a window, not what is active.

Which sources were read well. An item ends only when its lane was read successfully on this run. A lane is the item's
first source id, the key of that source in the program's health record. The health record comes from --health, or
from the feed's own `health` member; a lane counts as read when its last success is its last check and, when the entry
gives a state of its own, that state is fresh, late or up (a source whose items are withheld as stale ends nothing). With no health
record at all, every lane counts as read: safe only for a program that keeps a failed source's last items in its
feed. As a guard, a run whose feed has no items at all, with no health record, ends nothing. An item whose lane the
health record does not name can never end; the command warns, and --lane-map names source ids as lanes
(usembassy-*=us-embassy-alerts).

Subjects (kit 0.6.0). An item with a subject_id (contract revision 2.1) is kept under it, so a daily reading of the
same subject under a new dated id updates one open entry instead of logging new and ended every day; an item without
one is kept under its id, as before. Lines gain `subject_id` when the item has one. fill_last_change() (and
--fill-last-change) fills the items' last_change and last_change_at from the log for a program with no better
knowledge; the state records when each subject last moved, and `since`, the log's first run.

First written for Elements (13 Nov 2026) and moved here unchanged in format, so every program keeps the same log
and COP can gather them into one ledger."""
import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

FORMAT = "tic-history/1"
ENDED_DAYS = 7
RECENT_DAYS = 4                                    # ids ended this recently are not logged again by a catch-up
STATUS_KEYS = ("tier", "response_stage")           # a change here is a "changed" line
VOLATILE = ("published_at",)                       # a change only here is no change at all
TIER_RANK = {"routine": 0, "anomaly": 1, "warning": 2}


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _t(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except ValueError:
        return None


def lane(feature: dict) -> str | None:
    """The source lane an item comes from: its first source's `lane` when it names one (contract revision 2.1),
    otherwise that source's id, which is the lane's key in the health record."""
    src = (feature.get("properties") or {}).get("sources") or []
    first = (src[0] or {}) if src else {}
    return first.get("lane") or first.get("id")


def key(feature: dict) -> str | None:
    """The key an item is kept under: its subject_id when it has one (contract revision 2.1), so a daily reading of
    the same subject under a new dated id is an update and not a new item and an end; otherwise its id."""
    p = feature.get("properties") or {}
    return p.get("subject_id") or p.get("id")


def move(before: list | None, after: list) -> str:
    """raised, lowered or changed, for a move of [tier, response_stage]: the tier first (routine < anomaly <
    warning), then the rung's severity when the ladder is the same."""
    before = before or [None, None]
    t0, t1 = TIER_RANK.get(before[0], 0), TIER_RANK.get(after[0], 0)
    if t0 != t1:
        return "raised" if t1 > t0 else "lowered"
    s0, s1 = _severity(before[1]), _severity(after[1])
    if s0 is not None and s1 is not None and s0[0] == s1[0] and s0[1] != s1[1]:
        return "raised" if s1[1] > s0[1] else "lowered"
    return "changed"


def _severity(stage) -> tuple[str, int] | None:
    from . import vocab
    ladder, _, value = str(stage or "").partition(":")
    rung = vocab.ladders().get(ladder, {}).get("values", {}).get(value)
    return (ladder, rung["severity"]) if isinstance(rung, dict) and "severity" in rung else None


def mapped_lane(lane_map: dict):
    """A lane_of for programs whose source ids are finer than their health record: {"usembassy-*": "us-embassy-alerts"}
    names every source id that starts with usembassy- as the lane us-embassy-alerts. An exact id wins over a prefix;
    an id the map does not name keeps its own name."""
    exact = {k: v for k, v in (lane_map or {}).items() if not k.endswith("*")}
    prefixes = sorted(((k[:-1], v) for k, v in (lane_map or {}).items() if k.endswith("*")), key=lambda kv: -len(kv[0]))

    def lane_of(feature: dict):
        own = lane(feature)
        if own in exact:
            return exact[own]
        return next((v for pre, v in prefixes if own and own.startswith(pre)), own)
    return lane_of


def fingerprint(feature: dict, volatile: tuple = VOLATILE) -> str:
    """A hash of the item without the fields that change on every run (published_at, each source's accessed_at)."""
    p = dict(feature.get("properties") or {})
    for k in volatile:
        p.pop(k, None)
    p["sources"] = [{k: v for k, v in (s or {}).items() if k != "accessed_at"} for s in p.get("sources") or []]
    text = json.dumps({"geometry": feature.get("geometry"), "properties": p}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _line(at, change, entry, item, **extra):
    p = item.get("properties") or {}
    subject = {"subject_id": p["subject_id"]} if p.get("subject_id") else {}
    return {"format": FORMAT, "at": at, "change": change, "id": p.get("id"), **subject, "program": p.get("program"),
            "lane": entry["lane"], "first_seen": entry["first_seen"], "last_seen": entry["last_seen"],
            "peak_tier": entry["peak_tier"], "updates": entry["updates"], **extra, "item": item}


def fill_last_change(feed: dict, state: dict, since: str | None = None) -> int:
    """Fill last_change and last_change_at (contract revision 2.1) from the history state, on each feed item that
    does not state them itself; returns how many were filled. For a program with no better knowledge: a program
    that knows more (an issuer's own "raised", a notice's own issue time) states the fields and they are kept.

    state is the state after this run's update(). The rule, from the log's own record:
    - the item's state (tier and response_stage) moved since it opened: raised, lowered or changed, at that run;
    - it opened after the log's first run: new, at its first sighting;
    - it was there on the log's first run and has not moved since: none (standing as long as the log has watched).
    `since` is the log's first run (default: the state's `since`, written from kit 0.6.0; for an older log, pass
    first_run(root)). Without any, an item never seen to move reads new at its first sighting."""
    open_ = (state or {}).get("open") or {}
    since = since or (state or {}).get("since")
    n = 0
    for f in feed.get("features") or []:
        p = f.get("properties")
        if not isinstance(p, dict) or p.get("last_change") is not None:
            continue
        e = open_.get(key(f))
        if e is None or ((e.get("item") or {}).get("properties") or {}).get("id") != p.get("id"):
            e = open_.get(p.get("id")) or e      # kept under its own id (a second item of one subject)
        if e is None:
            continue
        lc, at = e.get("last_change"), e.get("last_change_at")
        if lc in (None, "new"):                  # never seen to move: new, unless there on the log's first run
            first = e.get("first_seen")
            lc, at = ("none", None) if since and first and first <= since else ("new", at or first)
        p["last_change"] = lc
        if at:
            p["last_change_at"] = at
        else:
            p.pop("last_change_at", None)
        n += 1
    return n


def first_run(root: Path) -> str | None:
    """The time of the first line in a program's log (its first run), for fill_last_change on a log begun before kit
    0.6.0. None when the log is empty."""
    days = sorted((Path(root) / "log").glob("*/*/*.jsonl*"))
    for p in days:
        opener = gzip.open if p.suffix == ".gz" else open
        with opener(p, "rt", encoding="utf-8") as fh:
            for s in fh:
                if s.strip():
                    return json.loads(s).get("at")
    return None


READ_STATES = ("fresh", "late", "up")              # a health entry's own state, when it gives one


def lanes_ok(health: dict) -> set:
    """Lanes read successfully on the run that wrote this health record: its last success is its last check, and, when
    the entry gives a state of its own, that state is fresh, late or up. A program that withholds a source's items
    while the source still answers (Cordon withholds a frozen warning list as "stale") marks it so, and its withheld
    items stay open instead of ending."""
    return {k for k, v in (health or {}).items()
            if isinstance(v, dict) and v.get("last_ok") and v.get("last_ok") == v.get("checked_at")
            and (v.get("state") is None or v.get("state") in READ_STATES)}


def update(state: dict, feed: dict, health: dict | None, now: datetime, caught: list | None = None, *,
           ok: set | None = None, lane_of=lane, volatile: tuple = VOLATILE,
           reading_key: str | None = None) -> tuple[dict, list]:
    """(new state, log lines) after one run. Pure: no files read or written.

    state   {"open": {id: entry}} from the last run ({} on the first)
    feed    the FeatureCollection just built
    health  the program's health record of this run ({lane: {"last_ok", "checked_at"}}); None when it has none
    caught  items issued since the last run and no longer active (built like feed items), from a catch-up query
    ok      the lanes read well this run, when the caller knows them some other way (overrides health)
    lane_of how to name an item's lane (default: its first source id)
    volatile  property names that change on every run and are no change at all
    reading_key  a property whose move is a "changed" line too (a new reading under the same id); its value before
             is in `was`. Kept apart from the status, so an item logged before the option was used is not
             reported as changed on the first run with it

    With neither health nor ok, every lane counts as read, except that a feed with no items ends nothing."""
    at = _stamp(now)
    open_ = dict((state or {}).get("open") or {})
    keep_from = _stamp(now - timedelta(days=RECENT_DAYS))
    recent = {k: v for k, v in ((state or {}).get("recently_ended") or {}).items() if v >= keep_from}
    lines = []
    features = feed.get("features") or []
    if ok is None and health is not None:
        ok = lanes_ok(health)
    blind = ok is None and not features           # nothing to say which lanes were read, and nothing came: end nothing
    dropped = {x.get("id") for x in feed.get("dropped") or []}
    seen = set()
    first_run = not open_ and not recent and not (state or {}).get("since")
    for f in features:
        p = f.get("properties") or {}
        iid = key(f)
        if iid in seen and p.get("id") and p["id"] not in seen:
            iid = p["id"]                    # a second item of the same subject in one feed: kept under its own id
        if not iid or iid in seen:
            continue
        seen.add(iid)
        if iid not in open_ and p.get("id") in open_ and p["id"] != iid and p["id"] not in seen:
            open_[iid] = open_.pop(p["id"])  # first run with subject_id: the item's open entry moves to its subject
        fp = fingerprint(f, volatile)
        e = open_.get(iid)
        if e is None:
            e = {"lane": lane_of(f), "first_seen": at, "last_seen": at, "hash": fp, "updates": 0,
                 "peak_tier": p.get("tier"), "status": [p.get(k) for k in STATUS_KEYS], "item": f,
                 "last_change": "none" if first_run else "new", "last_change_at": None if first_run else at}
            if reading_key:
                e["reading"] = p.get(reading_key)
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
        reading = p.get(reading_key) if reading_key else None
        read_moved = bool(reading_key) and "reading" in e and reading != e["reading"]
        if moved or read_moved:
            was = dict(zip(STATUS_KEYS, e.get("status") or [None, None]))
            if read_moved:
                was[reading_key] = e["reading"]
            lines.append(_line(at, "changed", e, f, was=was))
            if moved:              # last_change follows the state (tier, response_stage), not a new reading
                e.update({"last_change": move(e.get("status"), status), "last_change_at": at})
            e["status"] = status
        if reading_key:
            e["reading"] = reading
    for iid in sorted(set(open_) - seen):
        e = open_[iid]
        item_id = ((e.get("item") or {}).get("properties") or {}).get("id")
        if blind or iid in dropped or item_id in dropped or (ok is not None and e.get("lane") not in ok):
            continue           # its source failed this run, or the linter held it back: not ended
        lines.append(_line(at, "ended", e, e["item"], ended_at=end_time(e, now), end_reason="left the feed"))
        recent[iid] = at
        del open_[iid]
    for f in caught or []:
        p = f.get("properties") or {}
        iid = key(f)
        if not iid or iid in open_ or iid in seen or iid in recent:
            continue           # live now, or already ended (seen live, or caught on an earlier run)
        until = _t(p.get("valid_until"))
        end = _stamp(min(until, now)) if until else at
        e = {"lane": lane_of(f), "first_seen": p.get("data_as_of") or at, "last_seen": None,
             "hash": fingerprint(f, volatile), "updates": 0, "peak_tier": p.get("tier")}
        lines.append(_line(at, "new", e, f, seen_live=False))
        lines.append(_line(at, "ended", e, f, ended_at=end, end_reason="issued and ended between runs", seen_live=False))
        recent[iid] = at
    since = (state or {}).get("since") or (at if first_run else None)
    out = {"format": FORMAT, "updated_at": at, "recently_ended": dict(sorted(recent.items())), "open": open_}
    if since:
        out = {"format": FORMAT, "since": since, **{k: v for k, v in out.items() if k != "format"}}
    return out, lines


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
    return Path(root) / "log" / y / m / (f"{d}.jsonl.gz" if closed else f"{d}.jsonl")


def load_state(root: Path) -> dict:
    p = Path(root) / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"format": FORMAT, "open": {}}


def save_state(root: Path, state: dict) -> None:
    """One open item per line, sorted by id, so a run's commit touches only the lines that changed."""
    root = Path(root)
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
    for p in sorted((Path(root) / "log").glob("*/*/*.jsonl")):
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


def ended_collection(root: Path, state: dict, now: datetime, days: int = ENDED_DAYS, program: str | None = None,
                     name: str | None = None) -> dict:
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
    program = program or next((x.get("program") for x in last.values() if x.get("program")), None)
    name = name or (program or "this program").capitalize()
    return {"type": "FeatureCollection", "format": FORMAT, "program": program, "generated_at": _stamp(now),
            "window_days": days,
            "what": ("%s items that ended in the last %d days: they left the feed while their source was read "
                     "successfully, or were issued and ended between two runs. Not active: not drawn on the map and "
                     "not in the feed. Each keeps its last version; `history` gives first_seen, last_seen, ended_at "
                     "(the first run without it, or the item's own end) and end_reason. The full record is the "
                     "program's history log." % (name, days)),
            "features": feats}


def run(feed: dict, root: Path, now: datetime, health: dict | None = None, caught: list | None = None, *,
        fill: bool = False, **kw) -> list:
    """One run against the files in `root`: read the state, log the changes, close past days, save the state.
    Returns the lines written. With fill, the feed's items that do not state last_change get it from the log
    (fill_last_change), in place, before the lines are written, so the log carries the filled items too."""
    before = load_state(root)
    if not before.get("since") and (before.get("open") or before.get("recently_ended")):
        since = first_run(root)                       # a log begun before kit 0.6.0: its first line is its start
        if since:
            before = {**before, "since": since}
    state, lines = update(before, feed, health, now, caught, **kw)
    if fill:
        fill_last_change(feed, state)
    append_log(root, lines)
    close_days(root, now.strftime("%Y-%m-%d"))
    save_state(root, state)
    return lines


def run_time(feed: dict, wall: datetime | None = None) -> datetime:
    """The run's time when --now is not given (kit 0.6.3): the feed's own generated_at, so nothing the run stamps
    (first_seen, last_change_at) is later than the items' published_at, which the build set seconds before; the wall
    clock when the feed has no generated_at, or when generated_at is later than the wall clock."""
    wall = wall or datetime.now(timezone.utc)
    gen = _t(feed.get("generated_at"))
    return min(gen, wall) if gen else wall


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tic.py history", description="Log what changed in a feed since the last run.")
    ap.add_argument("feed", help="the feed just built (a tic-feed/2 FeatureCollection)")
    ap.add_argument("--dir", default="history", help="where the log and state.json live (default: history)")
    ap.add_argument("--health", help="the program's health record of this run ({lane: {last_ok, checked_at}}); "
                                     "default: the feed's own `health` member, if it has one")
    ap.add_argument("--lane-map", action="append", default=[], metavar="SOURCE=LANE",
                    help="name a source id (or a prefix ending in *) as a lane of the health record, e.g. "
                         "usembassy-*=us-embassy-alerts; repeat as needed")
    ap.add_argument("--ended", help="also write the items that ended in the last --days days to this file")
    ap.add_argument("--days", type=int, default=ENDED_DAYS)
    ap.add_argument("--now", help="the run's time, ISO 8601 UTC (default: the feed's generated_at, else now)")
    ap.add_argument("--reading-key", metavar="PROPERTY",
                    help="also log a changed line when this item property moves, e.g. data_as_of for a program "
                         "whose ids stay the same from one reading of a series to the next")
    ap.add_argument("--fill-last-change", action="store_true",
                    help="fill last_change and last_change_at (contract revision 2.1) from the log on items that do "
                         "not state them, and rewrite the feed file with them")
    a = ap.parse_args(argv)
    feed = json.loads(Path(a.feed).read_text(encoding="utf-8"))
    now = _t(a.now) if a.now else run_time(feed)
    if now is None:
        print(f"history: --now {a.now!r} is not a time")
        return 2
    health = json.loads(Path(a.health).read_text(encoding="utf-8")) if a.health else feed.get("health")
    root = Path(a.dir)
    lane_map = dict(x.split("=", 1) for x in a.lane_map if "=" in x)
    lines = run(feed, root, now, health, lane_of=mapped_lane(lane_map), reading_key=a.reading_key,
                fill=a.fill_last_change)
    if a.fill_last_change:
        Path(a.feed).write_text(json.dumps(feed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8",
                                newline="\n")
        n = sum(1 for f in feed.get("features") or [] if (f.get("properties") or {}).get("last_change"))
        print(f"history: last_change on {n} of {len(feed.get('features') or [])} items -> {a.feed}")
    n = {c: sum(1 for x in lines if x["change"] == c) for c in ("new", "changed", "ended")}
    how = "health record" if health is not None else "no health record: every source counted as read"
    print(f"history: {n['new']} new, {n['changed']} changed, {n['ended']} ended ({how}); "
          f"{len(load_state(root).get('open') or {})} open")
    if health is not None:
        unknown = {}
        for e in (load_state(root).get("open") or {}).values():
            if e.get("lane") not in health:
                unknown[e.get("lane")] = unknown.get(e.get("lane"), 0) + 1
        if unknown:
            print(f"history: WARNING {sum(unknown.values())} open items are in lanes the health record does not name, "
                  f"so they can never end; map them with --lane-map: {', '.join(sorted(str(k) for k in unknown))}")
    if a.ended:
        out = Path(a.ended)
        out.parent.mkdir(parents=True, exist_ok=True)
        coll = ended_collection(root, load_state(root), now, a.days, feed.get("program"))
        out.write_text(json.dumps(coll, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        print(f"history: {len(coll['features'])} ended in the last {a.days} days -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
