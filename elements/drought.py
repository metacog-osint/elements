"""The US Drought Monitor (weekly, maps valid Tuesday, released Thursday), produced jointly by the National Drought
Mitigation Center at the University of Nebraska-Lincoln, the US Department of Agriculture and NOAA. The site states no
licence; Elements credits all three and links to droughtmonitor.unl.edu.

- Statistics service: the percent of the US (including Alaska, Hawaii and Puerto Rico) in each category, cumulative
  (D2 means D2 or worse), for the last six weeks. One small request an hour.
- The current map (about 17 MB of polygons) is fetched only when the statistics show a new week, and kept snapped to a
  0.05-degree grid (about 5 km) with slivers dropped: about 400 KB, for display only."""
import csv
import io
import json
from datetime import datetime, timedelta, timezone

from .common import fetch_or_none

STATS = ("https://usdmdataservices.unl.edu/api/USStatistics/GetDroughtSeverityStatisticsByAreaPercent"
         "?aoi=total&startdate={start}&enddate={end}&statisticsType=1")
MAP_URL = "https://droughtmonitor.unl.edu/data/json/usdm_current.json"
PAGE = "https://droughtmonitor.unl.edu/"
MAP_MAX_BYTES = 64 * 1024 * 1024
STEP, MIN_AREA = 0.05, 0.02    # degrees, square degrees
CATEGORIES = {0: "Abnormally dry", 1: "Moderate drought", 2: "Severe drought", 3: "Extreme drought",
              4: "Exceptional drought"}


def stats_url(now: datetime) -> str:
    return STATS.format(start=(now - timedelta(days=42)).strftime("%m/%d/%Y"), end=now.strftime("%m/%d/%Y"))


def parse_stats(body: bytes) -> list[dict]:
    """Weeks, newest first: {'map_date': '2026-10-27', 'valid_end', 'none', 'd0'..'d4'} in percent of area."""
    rows = []
    for r in csv.DictReader(io.StringIO(body.decode("utf-8-sig", "replace"))):
        try:
            md = r["MapDate"].strip()
            rows.append({"map_date": f"{md[:4]}-{md[4:6]}-{md[6:8]}", "valid_end": (r.get("ValidEnd") or "").strip() or None,
                         "none": float(r["None"]), **{f"d{i}": float(r[f"D{i}"]) for i in range(5)}})
        except (KeyError, ValueError):
            continue
    return sorted(rows, key=lambda x: x["map_date"], reverse=True)


def _area(ring) -> float:
    return abs(sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))) / 2


def _snap(ring):
    out = []
    for x, y in ring:
        p = [round(round(x / STEP) * STEP, 3), round(round(y / STEP) * STEP, 3)]
        if not out or out[-1] != p:
            out.append(p)
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out if len(out) >= 4 else None


def simplify(doc: dict) -> list[dict]:
    """[{'dm': 0..4, 'coordinates': MultiPolygon coordinates}] snapped to the grid, slivers and specks dropped."""
    out = []
    for f in doc.get("features", []):
        g = f.get("geometry") or {}
        polys = g.get("coordinates") if g.get("type") == "MultiPolygon" else [g.get("coordinates")] if g.get("coordinates") else []
        keep = []
        for poly in polys:
            outer = _snap(poly[0])
            if not outer or _area(outer) < MIN_AREA:
                continue
            holes = [h for h in (_snap(r) for r in poly[1:]) if h and _area(h) >= MIN_AREA]
            keep.append([outer] + holes)
        dm = (f.get("properties") or {}).get("DM")
        if dm in CATEGORIES and keep:
            out.append({"dm": dm, "coordinates": keep})
    return sorted(out, key=lambda x: x["dm"])


def collect(old, now: datetime | None = None, fetch=fetch_or_none):
    """(record, problem). record: {'weeks': [...], 'map_date', 'polygons': [...]}. The map is fetched only for a new week."""
    now = now or datetime.now(timezone.utc)
    old = old if isinstance(old, dict) else {}
    body, err = fetch(stats_url(now), 40)
    if body is None:
        return old, f"statistics: {err}"
    weeks = parse_stats(body)
    if not weeks:
        return old, "statistics: no rows"
    rec = {**old, "weeks": weeks[:6]}
    if old.get("map_date") == weeks[0]["map_date"] and old.get("polygons"):
        return rec, None
    body, err = fetch(MAP_URL, 120, MAP_MAX_BYTES)
    if body is None:
        return rec, f"map: {err} (statistics are current; the map is from {old.get('map_date') or 'no week'})"
    try:
        polys = simplify(json.loads(body))
    except (ValueError, TypeError, IndexError) as e:
        return rec, f"map: parse: {type(e).__name__}"
    # usdm_current.json is the map the statistics' newest week describes, once both have been released
    rec.update({"map_date": weeks[0]["map_date"], "polygons": polys})
    return rec, None
