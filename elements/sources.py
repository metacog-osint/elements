"""The four Elements sources. Each parse() turns one response into plain records; each collect() returns
(records, error) and keeps the previous records when the source fails.

- USGS earthquakes, magnitude 4.5 and above, past 7 days (GeoJSON summary feed), with the PAGER impact alert.
- GDACS (EC Joint Research Centre and UN OCHA) multi-hazard alerts, past 14 days: earthquakes, tropical cyclones,
  floods, volcanoes and droughts at every alert level; wildfires only at orange or red (green fires number in the
  hundreds and say little).
- NOAA National Hurricane Center active storms (Atlantic and eastern Pacific).
- Copernicus Emergency Management Service rapid-mapping activations (the EU maps a disaster on request).
"""
import json
import re
from datetime import datetime, timedelta, timezone

from .common import country_at, fetch_or_none, iso, now_utc  # first: puts the doctrine kit on sys.path
from tic_doctrine import geo  # noqa: E402

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
GDACS_API = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
NHC_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
CEMS_URL = "https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations-info/?limit=50"
CEMS_PAGE = "https://rapidmapping.emergency.copernicus.eu/"
GDACS_TYPES = {"EQ": "earthquake", "TC": "tropical cyclone", "FL": "flood", "VO": "volcano", "DR": "drought",
               "WF": "wildfire"}


def _iso_ms(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return None


def _naive_utc(s) -> str | None:
    """GDACS and Copernicus give times without a zone; both publish in UTC."""
    if not s:
        return None
    s = str(s).strip().replace(" ", "T")
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?)", s)
    if not m:
        return None
    t = m.group(1)
    return (t if m.group(2) else t + ":00") + "Z"


def country_of(lon: float, lat: float) -> list[str]:
    cc = country_at(lat, lon)
    return [cc] if cc else []


# ---- USGS -------------------------------------------------------------------------------------------------------
def parse_usgs(doc: dict) -> list[dict]:
    out = []
    for f in doc.get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        c = g.get("coordinates") or []
        if len(c) < 2 or p.get("mag") is None:
            continue
        out.append({"id": f.get("id"), "mag": round(float(p["mag"]), 1), "place": p.get("place") or "",
                    "time": _iso_ms(p.get("time")), "updated": _iso_ms(p.get("updated")), "alert": p.get("alert"),
                    "tsunami": bool(p.get("tsunami")), "sig": p.get("sig"), "url": p.get("url"),
                    "depth_km": round(float(c[2]), 1) if len(c) > 2 and c[2] is not None else None,
                    "lon": round(float(c[0]), 3), "lat": round(float(c[1]), 3),
                    "countries": country_of(float(c[0]), float(c[1]))})
    return out


def collect_usgs(old, fetch=fetch_or_none):
    body, err = fetch(USGS_URL, 40)
    if body is None:
        return old or [], err
    try:
        return parse_usgs(json.loads(body)), None
    except ValueError as e:
        return old or [], f"parse: {e}"


# ---- GDACS ------------------------------------------------------------------------------------------------------
def gdacs_urls(now: datetime) -> list[str]:
    frm, to = (now - timedelta(days=14)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
    base = f"{GDACS_API}?fromdate={frm}&todate={to}"
    # GDACS returns at most 100 events a query. Every orange or red alert first; then green cyclones, floods,
    # volcanoes and droughts (green earthquakes are left to USGS, green wildfires number in the hundreds).
    return [f"{base}&eventlist=EQ;TC;FL;VO;DR;WF&alertlevel=Orange;Red",
            f"{base}&eventlist=TC;FL;VO;DR&alertlevel=Green"]


def parse_gdacs(doc: dict) -> list[dict]:
    out = []
    for f in doc.get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        c = g.get("coordinates") or []
        if g.get("type") != "Point" or len(c) < 2:
            continue
        urls = p.get("url") or {}
        sev = p.get("severitydata") or {}
        out.append({"id": f"{p.get('eventtype')}-{p.get('eventid')}", "type": p.get("eventtype"),
                    "kind": GDACS_TYPES.get(p.get("eventtype"), p.get("eventtype")),
                    "episode": p.get("episodeid"), "name": " ".join((p.get("name") or p.get("eventname") or "").split()),
                    # alertlevel is the event's highest alert so far; episodealertlevel is the latest episode's
                    "alert": (p.get("alertlevel") or "").lower() or None, "score": p.get("alertscore"),
                    "latest_alert": (p.get("episodealertlevel") or "").lower() or None,
                    "severity_value": sev.get("severity"), "severity_unit": sev.get("severityunit"),
                    "from": _naive_utc(p.get("fromdate")), "to": _naive_utc(p.get("todate")),
                    "current": str(p.get("iscurrent")).lower() == "true", "country": p.get("country"),
                    "severity": sev.get("severitytext"), "report": urls.get("report") if isinstance(urls, dict) else None,
                    "lon": round(float(c[0]), 3), "lat": round(float(c[1]), 3),
                    "countries": country_of(float(c[0]), float(c[1]))})
    return out


def collect_gdacs(old, now: datetime | None = None, fetch=fetch_or_none):
    now = now or datetime.now(timezone.utc)
    events, errors = {}, []
    for url in gdacs_urls(now):
        body, err = fetch(url, 60)
        if body is None:
            errors.append(err)
            continue
        if not body.strip():
            continue  # GDACS answers an empty body when nothing matches (no orange or red wildfires): none, not a failure
        try:
            for e in parse_gdacs(json.loads(body)):
                events[e["id"]] = e
        except ValueError as e:
            errors.append(f"parse: {e}")
    if errors and not events:
        return old or [], "; ".join(errors)
    return sorted(events.values(), key=lambda e: e["from"] or "", reverse=True), ("; ".join(errors) or None)


# ---- NHC --------------------------------------------------------------------------------------------------------
def parse_nhc(doc: dict) -> list[dict]:
    out = []
    for s in doc.get("activeStorms", []):
        try:
            lat, lon = float(s.get("latitudeNumeric")), float(s.get("longitudeNumeric"))
        except (TypeError, ValueError):
            continue
        adv = s.get("publicAdvisory") or {}
        out.append({"id": s.get("id"), "name": s.get("name"), "classification": s.get("classification"),
                    "intensity_kt": s.get("intensity"), "pressure_mb": s.get("pressure"),
                    "movement": f"{s.get('movementDir', '')} at {s.get('movementSpeed', '')} kt".strip(),
                    "updated": _naive_utc(s.get("lastUpdate")) if s.get("lastUpdate") else None,
                    "advisory": adv.get("url") if isinstance(adv, dict) else None,
                    "lon": round(lon, 2), "lat": round(lat, 2)})
    return out


def collect_nhc(old, fetch=fetch_or_none):
    body, err = fetch(NHC_URL, 40)
    if body is None:
        return old or [], err
    try:
        return parse_nhc(json.loads(body)), None
    except ValueError as e:
        return old or [], f"parse: {e}"


# ---- Copernicus EMS -----------------------------------------------------------------------------------------------
_NAMES = None


def name_to_iso(name: str) -> str | None:
    global _NAMES
    if _NAMES is None:
        from pathlib import Path
        p = Path(geo.__file__).resolve().parents[2] / "geo" / "countries.json"
        _NAMES = {c["name"].lower(): c["cc"] for c in json.loads(p.read_text(encoding="utf-8"))["countries"] if c.get("name")}
        _NAMES.update({"czech republic": "CZ", "czechia": "CZ", "bosnia and herzegovina": "BA", "united kingdom": "GB",
                       "democratic republic of the congo": "CD", "republic of the congo": "CG", "congo": "CG", "türkiye": "TR",
                       "turkey": "TR", "north macedonia": "MK", "russia": "RU", "south sudan": "SS"})
    return iso(_NAMES.get((name or "").strip().lower()))


def parse_cems(doc: dict) -> list[dict]:
    out = []
    for r in doc.get("results", []):
        m = re.match(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", r.get("centroid") or "")
        countries = r.get("countries")
        if isinstance(countries, str):  # "['Spain']"
            countries = re.findall(r"'([^']+)'", countries)
        out.append({"code": r.get("code"), "name": r.get("name"), "category": r.get("category"),
                    "event": _naive_utc(r.get("eventTime")), "activated": _naive_utc(r.get("activationTime")),
                    "updated": _naive_utc(r.get("lastUpdate")), "closed": str(r.get("closed")).lower() == "true",
                    "products": r.get("n_products"), "countries": [c for c in (name_to_iso(n) for n in countries or []) if c],
                    "lon": round(float(m.group(1)), 3) if m else None, "lat": round(float(m.group(2)), 3) if m else None})
    return out


def collect_cems(old, fetch=fetch_or_none):
    body, err = fetch(CEMS_URL, 40)
    if body is None:
        return old or [], err
    try:
        return parse_cems(json.loads(body)), None
    except ValueError as e:
        return old or [], f"parse: {e}"


def collect_all(prev: dict, when: str | None = None) -> dict:
    """{'usgs': (records, err), ...}; FIRMS gives one payload of cells rather than a list of records."""
    from . import firms, volcanoes, weather
    now = datetime.now(timezone.utc)
    return {"usgs": collect_usgs(prev.get("usgs")), "gdacs": collect_gdacs(prev.get("gdacs"), now),
            "nhc": collect_nhc(prev.get("nhc")), "cems": collect_cems(prev.get("cems")),
            "firms": firms.collect_firms(prev.get("firms"), now),
            "usgs_volcano": volcanoes.collect_usgs(prev.get("usgs_volcano")),
            "nws": weather.collect_nws(prev.get("nws")), "spc": weather.collect_spc(prev.get("spc")),
            "when": when or now_utc()}
