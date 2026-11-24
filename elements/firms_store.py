"""The hourly store of FIRMS half-degree cells (decided 19 Nov 2026).

One gzipped JSON file per UTC hour, in a monthly GitHub release `firms-cells-YYYY-MM`, never in git. Uploads are
create-only: an hour already stored is left alone, so a later run or a rebuild can never replace what is there. An
hour holds the 24-hour window ending at that run, in the same columns as the page's data/fires.json.

Files rebuilt from NASA's public 7-day files say `"backfilled": true`. They hold near-real-time detections only, so
they lack the real-time rows a live run adds, and can include detections a live run at that hour had not yet received."""
import gzip
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import firms

FORMAT = "elements-firms-cells/1"
FRESH = timedelta(hours=2)    # a window older than this is a kept copy, not this run's read


def release_tag(t: datetime) -> str:
    return t.strftime("firms-cells-%Y-%m")


def asset_name(t: datetime) -> str:
    return t.strftime("firms-cells-%Y%m%dT%HZ.json.gz")


def snapshot(payload: dict, backfilled: bool = False, note: str | None = None) -> dict:
    """What is stored for one hour: the cells and how they were read, without the daily counts (kept in
    data/firms_daily.json) or the key's transaction counts."""
    out = {"format": FORMAT, "backfilled": backfilled, "window": payload["window"], "detections": payload["detections"],
           "newest": payload.get("newest"), "cell_deg": payload["cell_deg"], "via": payload.get("via") or {},
           "columns": payload["columns"], "cells": payload["cells"]}
    if note:
        out["note"] = note
    return out


def encode(snap: dict) -> bytes:
    """Gzip with no timestamp, so the same snapshot always gives the same bytes."""
    return gzip.compress(json.dumps(snap, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9, mtime=0)


def window_end(payload: dict) -> datetime | None:
    try:
        return datetime.strptime(payload["window"][1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _gh(args, run=subprocess.run):
    return run(["gh", *args], capture_output=True, text=True, timeout=120)


def existing_assets(tag: str, run=subprocess.run) -> set | None:
    """Asset names in the month's release; an empty set when the release does not exist; None when GitHub can't say."""
    r = _gh(["release", "view", tag, "--json", "assets", "--jq", ".assets[].name"], run)
    if r.returncode == 0:
        return {x for x in r.stdout.split() if x}
    return set() if "not found" in (r.stderr or "").lower() else None


def ensure_release(tag: str, run=subprocess.run) -> bool:
    notes = ("Hourly NASA FIRMS VIIRS detections in half-degree cells, 24-hour window per file (format " + FORMAT + "). "
             "Detections are not fires. Files marked backfilled were rebuilt from NASA's public 7-day files. "
             "Data: NASA FIRMS (LANCE, Earth Science Data and Information System).")
    return _gh(["release", "create", tag, "--title", tag, "--notes", notes, "--latest=false"], run).returncode == 0


def publish(files: list[Path], tag: str, run=subprocess.run) -> tuple[int, int, str | None]:
    """(uploaded, already there, problem). Never replaces an asset: `gh release upload` without --clobber refuses."""
    have = existing_assets(tag, run)
    if have is None:
        return 0, 0, f"could not read release {tag}"
    if not have and not ensure_release(tag, run) and existing_assets(tag, run) is None:
        return 0, 0, f"could not create release {tag}"
    todo = [f for f in files if f.name not in have]
    done = 0
    for f in todo:
        if _gh(["release", "upload", tag, str(f)], run).returncode != 0:
            return done, len(files) - len(todo), f"upload failed at {f.name}"
        done += 1
    return done, len(files) - len(todo), None


def store_run(payload: dict, out_dir: Path, now: datetime | None = None, run=subprocess.run) -> str:
    """Store this run's cells under its UTC hour; the first run of an hour wins. Returns one line for the log."""
    now = now or datetime.now(timezone.utc)
    end = window_end(payload or {})
    if not payload or not payload.get("cells") or end is None:
        return "firms store: no cells this run, nothing stored"
    if now - end > FRESH:
        return f"firms store: cells are a kept copy from {payload['window'][1]}, nothing stored"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / asset_name(end)
    path.write_bytes(encode(snapshot(payload)))
    up, there, problem = publish([path], release_tag(end), run)
    if problem:
        raise RuntimeError(problem)
    return f"firms store: {path.name} {'stored' if up else 'already there'} ({path.stat().st_size:,} bytes)"


def rebuild_hour(dets: list[tuple], end: datetime, via: dict, note: str) -> dict:
    """One hour rebuilt with the live aggregation. It is given the detections of the window's UTC day and the day
    before, up to the window's end, as a live run's two-day read is, so a cell's country is placed the same way."""
    first = (end - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    payload = firms.aggregate([d for d in dets if first <= d[2] <= end], end)
    payload["via"] = via
    return snapshot(payload, backfilled=True, note=note)
