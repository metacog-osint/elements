"""Elements command line. Standard library only.

    python tools/elements.py collect    fetch every source into data/ (a failing source keeps its last data)
    python tools/elements.py history    log what changed against the last run in history/ (new, changed, ended)
    python tools/elements.py firms-store  store this run's FIRMS cells in the month's release (create-only, one per hour)
    python tools/elements.py build      write site/ (map page, feed.geojson, ended.geojson) from data/ and history/
    python tools/elements.py check      the feed passes the doctrine kit's linter; registers are valid
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, firms, firms_store, history, meteoalarm, meteoalarm_log, nrc, sources, weather, wider  # noqa: E402
from elements.common import country_name, health, load, now_utc, save  # noqa: E402
from tic_doctrine import contract, geo, registers  # noqa: E402
from tic_doctrine.history import first_run  # noqa: E402

SRC, OUT, HIST = ROOT / "site_src", ROOT / "site", ROOT / "history"
LANES = {"usgs": "usgs-earthquakes", "gdacs": "gdacs", "nhc": "nhc", "cems": "copernicus-ems", "firms": "nasa-firms",
         "usgs_volcano": "usgs-volcanoes", "nws": "nws-alerts", "spc": "spc-outlook", "tsunami": "noaa-tsunami",
         "usdm": "us-drought-monitor", "meteoalarm": "meteoalarm", "emsc": "emsc", "nifc": "nifc-wfigs",
         "nrc_events": "nrc-events", "nrc_status": "nrc-reactor-status"}
COMPACT = {"usdm", "firms", "meteoalarm"}   # mostly coordinates: indenting them would triple their size


def drought_summary(rec) -> str:
    w = (rec or {}).get("weeks") or [] if isinstance(rec, dict) else []
    return f"week of {w[0]['map_date']}: {w[0]['d1']}% in drought, map of {rec.get('map_date') or 'no week'}" if w else "no data"


def status_summary(records) -> str:
    """The NRC status lane's detail: its newest report and how many units it gives."""
    s = nrc.summary(records or [])
    return (f"{len(records)} report dates, newest {s['date']}: {s['units']} units, {s['zero']} at 0%" if s
            else "no data")


def read_this_run(records, err, prev_records) -> bool:
    """Whether a source counts as read in data/health.json (15 Nov 2026). Read: it answered with no error, or with an
    error that still left records read on this run (one FIRMS satellite, some MeteoAlarm countries, the drought map).
    Not read: nothing came, or the run kept the last good copy whole (the collector handed back the previous records,
    or said every country or centre failed). Before this, a kept copy counted as read, so the history step, and COP's
    ledger from the feed's health block, took the kept items as seen again on every failed run."""
    if not err:
        return True
    if not records or records is prev_records:
        return False
    return not str(err).startswith("every ")


def collect() -> dict:
    when = now_utc()
    prev = {k: (load(f"{k}.json", {}) or {}).get("records") for k in LANES}
    nws_last_ok = ((load("health.json", {}) or {}).get(LANES["nws"]) or {}).get("last_ok")
    # The NWS catch-up: Severe and Extreme alerts issued since the last good read, active or not. The history step
    # logs the ones no longer active (issued and ended between runs). Read before the active list, so an alert issued
    # in between is in the active list rather than taken for ended. Its own file, not a health lane.
    start = weather.catchup_start(nws_last_ok, datetime.now(timezone.utc))
    caught, caught_err = weather.collect_nws_since(start)
    caught_at = now_utc()
    got = sources.collect_all(prev, when)
    # active_error: health counts a lane as read when an error still left records read on this run (a partial read),
    # so the history step needs to know whether this run's active list is fresh before it calls anything "no longer
    # active".
    save("nws_recent.json", {"fetched_at": caught_at, "start": start, "error": caught_err,
                             "active_error": got["nws"][1], "records": caught})
    summary = {}
    for k, src in LANES.items():
        records, err = got[k]
        if records is not prev[k]:
            save(f"{k}.json", {"records": records}, compact=k in COMPACT)
        detail = (firms.summary(records) if k == "firms" else drought_summary(records) if k == "usdm"
                  else meteoalarm.summary(records) if k == "meteoalarm"
                  else status_summary(records) if k == "nrc_status" else f"{len(records)} records")
        if err:
            detail = f"{detail} ({err})" if records else err
        health(src, read_this_run(records, err, prev[k]), detail, when)
        summary[k] = detail
    summary["nws catch-up"] = caught_err or f"{len(caught)} alerts issued since {start}"
    fp = got["firms"][0]
    if fp is not prev["firms"] and fp.get("daily"):
        old = load("firms_daily.json", {})
        new = firms.update_history(old, fp, when[:10])
        if new != old:
            save("firms_daily.json", new)  # committed: the baseline for fire anomalies (data/firms.json is not)
    return summary


def data() -> dict:
    h = load("health.json", {})
    return {k: {"records": (load(f"{k}.json", {}) or {}).get("records") or [], "fetched_at": (h.get(src) or {}).get("last_ok")}
            for k, src in LANES.items()} | {"health": h}


def caught_items(d: dict, now: datetime) -> list:
    """Feed items for NWS alerts the catch-up found that are not active now, linted like the feed. None unless the
    active read itself succeeded this run (otherwise "not active" would mean "not read")."""
    rec = load("nws_recent.json", {}) or {}
    err = rec.get("error") or ""
    if LANES["nws"] not in history.lanes_ok(d["health"]) or (err and not err.startswith("partial:")) \
            or rec.get("active_error") or "active_error" not in rec:
        return []
    active = {r["id"] for r in d["nws"]["records"] or []}
    gone = [r for r in rec.get("records") or [] if r.get("id") not in active]
    items = feed._weather_items({"nws": {"records": gone, "fetched_at": rec.get("fetched_at")}}, now)
    regs = registers.ids(ROOT / "doctrine")
    return [x for x in items if not any(sev == "error" for _, sev, _ in contract.check(x, regs))]


def log_history(now: datetime | None = None) -> list:
    """Compare the feed of this run's data with the items open after the last run; append the changes to the log."""
    now = now or datetime.now(timezone.utc)
    d = data()
    fc = feed.build(d, now)
    state, lines = history.update(history.load_state(HIST), fc, d["health"], now, caught_items(d, now))
    history.append_log(HIST, lines)
    history.close_days(HIST, now.strftime("%Y-%m-%d"))
    history.save_state(HIST, state)
    # Yellow MeteoAlarm warnings are not feed items: append them to their own archive (history/meteoalarm/).
    meteoalarm_log.update(HIST / "meteoalarm", d["meteoalarm"]["records"], now)
    return lines


def state_boxes(rings: list) -> list[list[float]]:
    """[west, south, east, north] boxes for a state's rings, one for its rings east of 0 degrees and one for those
    west of it, so a state across 180 degrees (Alaska) gets two boxes instead of one around the world. (Cordon's.)"""
    out = {}
    for ring in rings:
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        b = [min(xs), min(ys), max(xs), max(ys)]
        side = "e" if b[0] >= 0 else "w"
        o = out.get(side)
        out[side] = b if o is None else [min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3])]
    return [out[k] for k in sorted(out)]


def states_json() -> dict:
    """The Area menu's states (tic-area.js): code, name and boxes, from the kit's Natural Earth state outlines."""
    subs = json.loads(geo.SUBDIVISIONS.read_text(encoding="utf-8"))["subdivisions"]
    return {"source": "doctrine kit geo/subdivisions.json (Natural Earth 1:10m, public domain): code, name and boxes "
                      "only (one box per side of 180 degrees, so Alaska's Aleutians do not make a box around the world)",
            "states": [{"code": s["code"], "name": s["name"], "boxes": state_boxes(s["rings"])} for s in subs]}


def build() -> dict:
    d = data()
    now = datetime.now(timezone.utc)
    # Contract revision 2.1: last_change is filled from the history state the history step just wrote (it runs
    # first), on the items that do not state it; the log's first run (13 Nov 2026) marks what was standing then.
    state = history.load_state(HIST)
    fc = feed.build(d, now, state=state, since=state.get("since") or first_run(HIST))
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "geo").mkdir(exist_ok=True)
    (OUT / "geo" / "states.json").write_text(json.dumps(states_json(), separators=(",", ":")) + "\n",
                                           encoding="utf-8", newline="\n")
    (OUT / "data" / "feed.geojson").write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")) + "\n",
                                               encoding="utf-8", newline="\n")
    (OUT / "data" / "health.json").write_text(json.dumps(d["health"], indent=1) + "\n", encoding="utf-8", newline="\n")
    ended = history.ended_collection(HIST, state, now)
    (OUT / "data" / "ended.geojson").write_text(json.dumps(ended, ensure_ascii=False, separators=(",", ":")) + "\n",
                                                encoding="utf-8", newline="\n")
    fp = d["firms"]["records"] or {}
    fires = {k: fp.get(k) for k in ("window", "detections", "newest", "cell_deg", "columns", "cells", "via")}
    fires["names"] = {cc: country_name(cc) for cc in sorted({c[7] for c in fp.get("cells") or [] if c[7]})}
    wildfires = {"fires": [{k: w.get(k) for k in ("name", "acres", "contained", "discovered", "updated", "state", "county", "lon", "lat")}
                           for w in d["nifc"]["records"] or []]}
    (OUT / "data" / "wildfires.json").write_text(json.dumps(wildfires, ensure_ascii=False, separators=(",", ":")) + "\n",
                                                 encoding="utf-8", newline="\n")
    dr = d["usdm"]["records"] or {}
    drought = {"map_date": dr.get("map_date") if isinstance(dr, dict) else None,
               "polygons": dr.get("polygons") or [] if isinstance(dr, dict) else []}
    (OUT / "data" / "drought.json").write_text(json.dumps(drought, separators=(",", ":")) + "\n",
                                               encoding="utf-8", newline="\n")
    (OUT / "data" / "reactors.json").write_text(json.dumps(nrc.reactors_map(d["nrc_status"]["records"] or []),
                                                           ensure_ascii=False, separators=(",", ":")) + "\n",
                                                encoding="utf-8", newline="\n")
    (OUT / "data" / "fires.json").write_text(json.dumps(fires, ensure_ascii=False, separators=(",", ":")) + "\n",
                                             encoding="utf-8", newline="\n")
    (OUT / "data" / "meteoalarm.json").write_text(json.dumps(warnings_map(d["meteoalarm"]), ensure_ascii=False,
                                                             separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return fc


def warnings_map(src: dict, now: datetime | None = None) -> dict:
    """Every MeteoAlarm warning in force, yellow to red, for the map layer (the feed carries orange and red one by
    one, and yellow as a count per country)."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    keep = ("id", "country", "colour", "level", "type", "sender", "headline", "areas", "onset", "expires", "web",
            "credit", "precision", "points", "polygons")
    live = [r for r in src.get("records") or [] if (r.get("expires") or "") > stamp]
    return {"fetched_at": src.get("fetched_at"), "names": {cc: country_name(cc) for cc in sorted({r["country"] for r in live})},
            "warnings": [{k: r.get(k) for k in keep} for r in sorted(live, key=lambda r: r["level"])]}


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
    if cmd == "history":
        lines = log_history()
        n = {c: sum(1 for x in lines if x["change"] == c) for c in ("new", "changed", "ended")}
        print(f"history: {n['new']} new, {n['changed']} changed, {n['ended']} ended "
              f"({sum(1 for x in lines if x.get('seen_live') is False) // 2} caught between runs)")
        # Record-only lanes outside the feed (ideas#233). A failed lane is a warning and never fails this step.
        for line in wider.update_all(HIST, datetime.now(timezone.utc)):
            print(("::warning::" if "failed" in line or "partial" in line or "page " in line else "") + line)
        return 0
    if cmd == "firms-store":
        print(firms_store.store_run((load("firms.json", {}) or {}).get("records") or {}, ROOT / ".firms-cells"))
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
