"""US weather hazards: National Weather Service alerts rated Severe or Extreme, and the Storm Prediction Center's Day 1
categorical convective outlook. Both US public domain.

- NWS (api.weather.gov, active alerts, actual, new and updated): only CAP severity Severe or Extreme is kept. Messages
  for one event (one VTEC office, phenomenon, significance and event number) are merged, so an event with several
  segments is one record. Storm-based warnings carry their own polygon; the rest name counties (SAME codes), which are
  placed at each county's Census internal point (catalog/us_counties.json, tools/build_counties.py).
- SPC Day 1 categorical outlook: one record per risk area from Marginal (1 of 5) to High (5 of 5). General
  thunderstorm areas are not risk categories and are left out."""
import json
import re
from functools import lru_cache

from .common import ROOT, fetch_or_none

NWS_URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert,update"
SPC_URL = "https://www.spc.noaa.gov/products/outlook/day1otlk_cat.lyr.geojson"
SPC_PAGE = "https://www.spc.noaa.gov/products/outlook/day1otlk.html"
KEEP = ("Severe", "Extreme")
SPC_LEVELS = {"MRGL": 1, "SLGT": 2, "ENH": 3, "MDT": 4, "HIGH": 5}
TERRITORY = {"72": "PR", "78": "VI", "66": "GU", "60": "AS", "69": "MP"}   # state FIPS -> ISO, otherwise US
# /k.aaa.cccc.pp.s.####.  product class, action (NEW, CON, EXT...), office, phenomenon, significance, event number
VTEC_RE = re.compile(r"/[OTEX]\.[A-Z]{3}\.([A-Z0-9]{4})\.([A-Z]{2})\.([A-Z])\.(\d{4})\.")


@lru_cache(maxsize=1)
def counties() -> dict:
    p = ROOT / "catalog" / "us_counties.json"
    return json.loads(p.read_text(encoding="utf-8"))["counties"] if p.exists() else {}


def _utc(s) -> str | None:
    from .common import to_utc
    return to_utc(s) if s else None


def _round_geom(g):
    def r(c):
        return [r(x) for x in c] if c and isinstance(c[0], list) else [round(c[0], 3), round(c[1], 3)]
    return {"type": g["type"], "coordinates": r(g["coordinates"])} if g and g.get("coordinates") else None


def _centre(geom, pts):
    """A representative point: the mean of a polygon's outer-ring vertices, or of the county points."""
    if geom:
        ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
        return round(sum(x for x, _ in ring) / len(ring), 3), round(sum(y for _, y in ring) / len(ring), 3)
    if pts:
        return round(sum(p[0] for p in pts) / len(pts), 3), round(sum(p[1] for p in pts) / len(pts), 3)
    return None, None


def parse_nws(doc: dict) -> list[dict]:
    events = {}
    for f in doc.get("features", []):
        p = f.get("properties") or {}
        if p.get("severity") not in KEEP:
            continue
        vt = next((m for v in (p.get("parameters") or {}).get("VTEC") or [] for m in [VTEC_RE.search(v)] if m), None)
        sent = _utc(p.get("sent"))
        key = (f"{vt.group(1)}.{vt.group(2)}.{vt.group(3)}.{vt.group(4)}.{(sent or '')[:4]}" if vt
               else (p.get("id") or "").rsplit(".", 1)[-1][-16:])
        geoids = sorted({c[1:] for c in (p.get("geocode") or {}).get("SAME") or [] if len(c) == 6 and c.isdigit()})
        e = events.get(key)
        if e is None:
            e = events[key] = {"id": key, "event": p.get("event"), "severity": p.get("severity"),
                               "urgency": p.get("urgency"), "certainty": p.get("certainty"),
                               "sender": p.get("senderName"), "areas": [], "counties": [], "sent": sent,
                               "onset": _utc(p.get("onset")), "ends": _utc(p.get("ends") or p.get("expires")),
                               "url": p.get("@id"), "geometry": None, "vtec": bool(vt)}
        e["areas"] += [a.strip() for a in (p.get("areaDesc") or "").split(";") if a.strip() and a.strip() not in e["areas"]]
        e["counties"] = sorted(set(e["counties"]) | set(geoids))
        e["sent"] = max(e["sent"] or "", sent or "") or None
        e["ends"] = max(e["ends"] or "", _utc(p.get("ends") or p.get("expires")) or "") or None
        if p.get("severity") == "Extreme":
            e["severity"] = "Extreme"
        e["geometry"] = e["geometry"] or _round_geom(f.get("geometry"))
    out = []
    table = counties()
    for e in events.values():
        pts = [[table[g][1], table[g][0]] for g in e["counties"] if g in table]
        e["points"] = pts
        e["lon"], e["lat"] = _centre(e["geometry"], pts)
        e["countries"] = sorted({TERRITORY.get(g[:2], "US") for g in e["counties"]}) or ["US"]
        out.append(e)
    return sorted(out, key=lambda e: (e["severity"] != "Extreme", e["event"] or "", e["sent"] or ""))


def parse_spc(doc: dict) -> list[dict]:
    out = []
    for f in doc.get("features", []):
        p = f.get("properties") or {}
        label = (p.get("LABEL") or "").upper()
        if label not in SPC_LEVELS:
            continue
        out.append({"label": label, "name": p.get("LABEL2") or label, "level": SPC_LEVELS[label],
                    "valid": _spc_time(p.get("VALID")), "expires": _spc_time(p.get("EXPIRE")),
                    "issued": _spc_time(p.get("ISSUE")), "fill": p.get("fill"), "stroke": p.get("stroke"),
                    "geometry": _round_geom(f.get("geometry"))})
    return out


def _spc_time(s) -> str | None:
    m = re.match(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})$", str(s or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:00Z" if m else None


def _collect(url, parse, old, fetch, timeout=60):
    body, err = fetch(url, timeout)
    if body is None:
        return old or [], err
    try:
        return parse(json.loads(body)), None
    except (ValueError, KeyError, TypeError, IndexError) as e:
        return old or [], f"parse: {type(e).__name__}: {e}"


def collect_nws(old, fetch=fetch_or_none):
    return _collect(NWS_URL, parse_nws, old, fetch)


def collect_spc(old, fetch=fetch_or_none):
    return _collect(SPC_URL, parse_spc, old, fetch, 40)
