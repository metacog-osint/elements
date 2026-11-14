"""Build Elements' history log from its own git history: every commit of data/ since the first, replayed in order
through the same feed builder and the same history step a live run uses. Standard library only.

    python tools/history_backfill.py [--rev origin/main] [--force]
    python tools/history_backfill.py --continue [--rev origin/main]   # only the data commits after backfilled_to

Each data commit stands for one run, at its commit time (the bot commits within a minute of collecting). Limits, said
in each line's `backfill` member and in the log's README: data/firms.json and data/meteoalarm.json are not in git, so
FIRMS and MeteoAlarm items start on the first live run; a run that changed no data made no commit, so times are those
of the next change; the NWS catch-up did not exist, so warnings issued and ended between two runs are missing; the
feed is built with today's code, so an item's wording can differ from what was published that day.

Run it on a fresh history/ (it refuses to overwrite one without --force). Re-run it on the latest main just before
the history step goes live, so the log has no gap."""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, history  # noqa: E402  (elements.common puts the doctrine kit on sys.path)

HIST = ROOT / "history"
BACKFILL = "rebuilt from git history (data/ commits); not a live run"


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout


def lanes() -> dict:
    spec = {}
    exec(compile(_lanes_source(), "lanes", "exec"), spec)
    return spec["LANES"]


def _lanes_source() -> str:
    """The LANES table from tools/elements.py, read as text so this tool needs no import of that script."""
    text = (ROOT / "tools" / "elements.py").read_text(encoding="utf-8")
    start = text.index("LANES = {")
    end = text.index("}", start) + 1
    return text[start:end]


def at_commit(sha: str, files: set, lane_map: dict) -> dict:
    def load(name):
        if f"data/{name}" not in files:
            return {}
        try:
            return json.loads(git("show", f"{sha}:data/{name}"))
        except (subprocess.CalledProcessError, ValueError):
            return {}
    h = load("health.json") or {}
    return {k: {"records": (load(f"{k}.json") or {}).get("records") or [], "fetched_at": (h.get(src) or {}).get("last_ok")}
            for k, src in lane_map.items()} | {"health": h}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rev", default="origin/main", help="the git revision whose data/ history is replayed")
    ap.add_argument("--force", action="store_true", help="replace an existing history/")
    ap.add_argument("--continue", dest="cont", action="store_true",
                    help="keep history/ and replay only the data commits after state.json's backfilled_to")
    a = ap.parse_args(argv)
    lane_map = lanes()

    def log(rng):
        return [ln.split() for ln in git("log", "--reverse", "--format=%H %cI", rng, "--", "data").splitlines()]
    n, skipped = {"new": 0, "changed": 0, "ended": 0}, []
    if a.cont:
        state = history.load_state(HIST)
        if not state.get("backfilled_to"):
            print("history/state.json has no backfilled_to: rebuild with --force")
            return 2
        commits = log(f"{state['backfilled_to']}..{a.rev}")
        last = datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00"))
    else:
        if (HIST / "state.json").exists() and not a.force:
            print("history/ exists: use --force to rebuild it from scratch, or --continue to add the newer runs")
            return 2
        if HIST.exists():
            shutil.rmtree(HIST)
        commits = log(a.rev)
        state, last = {"format": history.FORMAT, "open": {}}, None
    for sha, when in commits:
        now = datetime.fromisoformat(when).astimezone(timezone.utc).replace(microsecond=0)
        if last and now <= last:
            now = last + timedelta(seconds=1)  # keep runs in order when a rebase reordered commit times
        files = set(git("ls-tree", "-r", "--name-only", sha, "data").split())
        d = at_commit(sha, files, lane_map)
        try:
            fc = feed.build(d, now)
        except Exception as e:  # noqa: BLE001 - an old data shape this code cannot read: skip that run, say so
            skipped.append(f"{sha[:7]} {type(e).__name__}")
            continue
        state, lines = history.update(state, fc, d["health"], now)
        for x in lines:
            x["backfill"] = BACKFILL
            n[x["change"]] += 1
        history.append_log(HIST, lines)
        last = now
    history.close_days(HIST, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    state["backfilled_to"] = commits[-1][0] if commits else state.get("backfilled_to")
    state["backfill_skipped"] = state.get("backfill_skipped", 0) + len(skipped)
    history.save_state(HIST, state)
    every = log(a.rev)
    (HIST / "README.md").write_text(README.format(first=every[0][1][:10] if every else "-",
                                                  last=last.strftime("%Y-%m-%dT%H:%M:%SZ") if last else "-",
                                                  runs=len(every) - state["backfill_skipped"]),
                                    encoding="utf-8", newline="\n")
    print(f"{len(commits)} data commits replayed ({len(skipped)} skipped{': ' + ', '.join(skipped[:5]) if skipped else ''}); "
          f"{n['new']} new, {n['changed']} changed, {n['ended']} ended; {len(state['open'])} open at the end")
    return 0


README = """# Elements history

Every item Elements has published, kept after it leaves the feed: Elements' own historical record, part of The
Intelligence Company's historical dataset. Written by `elements/history.py` (format `tic-history/1`).

- `log/YYYY/MM/DD.jsonl` (today) and `DD.jsonl.gz` (closed days, written once): one line per change, `new`,
  `changed` (tier or response stage moved) or `ended` (left the feed while its source was read successfully, or an
  NWS alert issued and ended between two runs). Each line carries the full contract-v2 item as it stood, with
  first_seen, last_seen, ended_at, end_reason, peak_tier and the number of updates. Times UTC.
- `state.json`: the items open after the last run.
- The site serves the last 7 days of ended items at `data/ended.geojson`, not drawn on the map and not in the feed.

From {first} to {last} the log was rebuilt from this repository's git history of `data/` ({runs} runs) by
`tools/history_backfill.py`; those lines carry a `backfill` member. Limits of that part: FIRMS and MeteoAlarm data
were not in git, so their items start on the first live run; a run that changed no data made no commit; warnings
issued and ended between two runs are missing (the live catch-up started later); the items were rebuilt with the
code of the backfill, so their wording can differ from what was published at the time.
"""


if __name__ == "__main__":
    sys.exit(main())
