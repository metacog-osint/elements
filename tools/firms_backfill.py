"""Rebuild hourly FIRMS cell files from NASA's public 7-day CSV files. Writes files only; upload is separate.

    python tools/firms_backfill.py <folder with the 7-day CSVs> <output folder> <first hour> <last hour>

Hours are UTC, written 2026-11-17T00. Each file holds the 24-hour window ending at that hour.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import firms, firms_store  # noqa: E402

FILES = {"VIIRS_NOAA20_NRT": "J1_VIIRS_C2_Global_7d.csv", "VIIRS_NOAA21_NRT": "J2_VIIRS_C2_Global_7d.csv",
         "VIIRS_SNPP_NRT": "SUOMI_VIIRS_C2_Global_7d.csv"}
NOTE = ("Rebuilt from NASA's public 7-day files: near-real-time detections only, so without the real-time rows a live "
        "run adds (about 2% fewer detections in the window checked), and possibly with some a live run at this hour had "
        "not yet received.")


def hour(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def main(argv) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    src, out, t, last = Path(argv[0]), Path(argv[1]), hour(argv[2]), hour(argv[3])
    dets, via = [], {}
    for sensor, name in FILES.items():
        rows = firms.parse((src / name).read_bytes())
        via[sensor] = "public 7-day file" if rows else "public 7-day file (no rows)"
        dets += rows
    dets.sort(key=lambda d: d[2])
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    while t <= last:
        snap = firms_store.rebuild_hour(dets, t, via, NOTE)
        (out / firms_store.asset_name(t)).write_bytes(firms_store.encode(snap))
        n += 1
        t += timedelta(hours=1)
    print(f"{n} hour files in {out}; {len(dets):,} detections read; {via}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
