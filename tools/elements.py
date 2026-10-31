"""Elements command line. Standard library only.

    python tools/elements.py collect    fetch every source into data/ (a failing source keeps its last data)
    python tools/elements.py build      write site/ (map page, feed.geojson) from data/
    python tools/elements.py check      the feed passes the doctrine kit's linter; registers are valid
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, sources  # noqa: E402
from elements.common import health, load, now_utc, save  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402

SRC, OUT = ROOT / "site_src", ROOT / "site"
LANES = {"usgs": "usgs-earthquakes", "gdacs": "gdacs", "nhc": "nhc", "cems": "copernicus-ems"}


def collect() -> dict:
    when = now_utc()
    prev = {k: (load(f"{k}.json", {}) or {}).get("records") for k in LANES}
    got = sources.collect_all(prev, when)
    summary = {}
    for k, src in LANES.items():
        records, err = got[k]
        if records is not prev[k]:
            save(f"{k}.json", {"records": records})
        health(src, not err or bool(records), err or f"{len(records)} records", when)
        summary[k] = err or f"{len(records)} records"
    return summary


def data() -> dict:
    h = load("health.json", {})
    return {k: {"records": (load(f"{k}.json", {}) or {}).get("records") or [], "fetched_at": (h.get(src) or {}).get("last_ok")}
            for k, src in LANES.items()} | {"health": h}


def build() -> dict:
    d = data()
    fc = feed.build(d, datetime.now(timezone.utc))
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "data" / "feed.geojson").write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")) + "\n",
                                               encoding="utf-8", newline="\n")
    (OUT / "data" / "health.json").write_text(json.dumps(d["health"], indent=1) + "\n", encoding="utf-8", newline="\n")
    return fc


def check() -> list[str]:
    errs = [f"registers: {e}" for e in registers.check(ROOT / "doctrine")]
    fc = feed.build(data())
    errs += [f"dropped {x['id']}: {x['errors']}" for x in fc["dropped"]]
    regs = registers.ids(ROOT / "doctrine")
    for f in fc["features"]:
        errs += [f"{f['properties']['id']}: {m}" for _, sev, m in contract.check(f, regs) if sev == "error"]
    return errs


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["help"])[0]
    if cmd == "collect":
        for k, v in collect().items():
            print(f"{k}: {v}")
        return 0
    if cmd == "build":
        fc = build()
        print(f"site/ written: {len(fc['features'])} feed items, {len(fc['dropped'])} dropped")
        return 0
    if cmd == "check":
        errs = check()
        for e in errs[:50]:
            print("  -", e)
        print("Elements check:", "PASS" if not errs else f"FAIL ({len(errs)} problems)")
        return 1 if errs else 0
    print(__doc__)
    return 0 if cmd == "help" else 2


if __name__ == "__main__":
    sys.exit(main())
