"""Elements' feed in contract v2 (tic-feed/2). Every item is a measurement (kind observation) of what an authority
published, with its own alert ladder as response_stage (pager:*, gdacs:*, cems:*). An alert above the bottom rung
(PAGER yellow or worse, GDACS orange or red) is an anomaly against that ladder's baseline. Each item passes the
doctrine kit's linter or is dropped and listed."""
import json
import re
from datetime import datetime, timedelta, timezone
from functools import cache

from .common import ROOT, country_name, country_point  # first: puts the doctrine kit on sys.path
from tic_doctrine import CONTRACT, __version__ as KIT, contract, geo, registers, vocab  # noqa: E402
from . import rev21  # noqa: E402

METHOD = "elements-feed-1.2"
CEMS_DAYS = 60
SRC = {
    "usgs": {"id": "usgs-earthquakes", "publisher": "US Geological Survey", "licence": "US public domain", "grade": "A1",
             "independence_group": "usgs", "source_type": "official measurement",
             "descriptor": "Earthquake origin, magnitude and PAGER impact alert (ComCat summary feed)"},
    "gdacs": {"id": "gdacs", "publisher": "GDACS (EC Joint Research Centre and UN OCHA)",
              "licence": "GDACS terms: reuse with attribution (not re-checked)", "grade": "A2",
              "independence_group": "gdacs", "source_type": "automated alert",
              "descriptor": "Global Disaster Alert and Coordination System alert, computed from hazard models"},
    "nhc": {"id": "nhc", "publisher": "NOAA National Hurricane Center", "url": "https://www.nhc.noaa.gov/",
            "licence": "US public domain", "grade": "A1", "independence_group": "noaa", "source_type": "official forecast centre",
            "descriptor": "Active tropical cyclone position and intensity"},
    "cems": {"id": "copernicus-ems", "publisher": "Copernicus Emergency Management Service (European Union)",
             "url": "https://rapidmapping.emergency.copernicus.eu/", "licence": "Copernicus: free and open, with attribution (© European Union)",
             "grade": "A1", "independence_group": "copernicus", "source_type": "official activation",
             "descriptor": "Rapid-mapping activation: an authority asked the EU to map a disaster"},
    "firms": {"id": "nasa-firms", "publisher": "NASA FIRMS (LANCE, Earth Science Data and Information System)",
              "url": "https://firms.modaps.eosdis.nasa.gov/", "licence": "NASA open data, with acknowledgement of LANCE FIRMS",
              "grade": "A2", "independence_group": "nasa", "source_type": "satellite detection",
              "descriptor": "VIIRS active fire and thermal-anomaly detections (NOAA-20, NOAA-21, Suomi-NPP)"},
}
SRC["usgs_volcano"] = {"id": "usgs-volcanoes", "publisher": "USGS Volcano Hazards Program", "licence": "US public domain",
                       "grade": "A1", "independence_group": "usgs", "source_type": "official alert",
                       "descriptor": "Volcano alert level and aviation colour code from the responsible USGS observatory"}
SRC["nws"] = {"id": "nws-alerts", "publisher": "NOAA National Weather Service", "url": "https://www.weather.gov/",
              "licence": "US public domain", "grade": "A1", "independence_group": "noaa", "source_type": "official warning",
              "descriptor": "CAP alert (warning, watch or advisory) rated Severe or Extreme, from api.weather.gov"}
SRC["spc"] = {"id": "spc-outlook", "publisher": "NOAA Storm Prediction Center", "url": "https://www.spc.noaa.gov/",
              "licence": "US public domain", "grade": "A1", "independence_group": "noaa", "source_type": "official forecast",
              "descriptor": "Day 1 categorical convective outlook (risk of organised severe thunderstorms)"}
SRC["tsunami"] = {"id": "noaa-tsunami", "publisher": "NOAA tsunami warning centres (NTWC, PTWC)", "url": "https://www.tsunami.gov/",
                  "licence": "US public domain", "grade": "A1", "independence_group": "noaa", "source_type": "official warning",
                  "descriptor": "Tsunami message (CAP): information statement, threat message, watch, advisory or warning"}
SRC["usdm"] = {"id": "us-drought-monitor", "publisher": "US Drought Monitor (NDMC University of Nebraska-Lincoln, USDA, NOAA)",
               "url": "https://droughtmonitor.unl.edu/", "licence": "Credit NDMC, USDA and NOAA (no licence stated; not verified)",
               "grade": "A2", "independence_group": "usdm", "source_type": "expert assessment",
               "descriptor": "Weekly drought categories D0 to D4, percent of US area (cumulative)"}
SRC["meteoalarm"] = {"id": "meteoalarm", "publisher": "MeteoAlarm (EUMETNET), from its members' national weather services",
                     "url": "https://meteoalarm.org/", "licence": "CC BY 4.0 (feeds.meteoalarm.org)", "grade": "A1",
                     "independence_group": "eumetnet", "source_type": "official warning",
                     "descriptor": "National weather service warning (CAP) with MeteoAlarm's awareness level and type"}
SRC["emsc"] = {"id": "emsc", "publisher": "European-Mediterranean Seismological Centre (EMSC)", "url": "https://www.seismicportal.eu/",
               "licence": "CC BY 4.0", "grade": "A1", "independence_group": "emsc", "source_type": "official measurement",
               "descriptor": "Earthquake origin and magnitude (seismicportal.eu FDSN event service)"}
SRC["nifc"] = {"id": "nifc-wfigs", "publisher": "National Interagency Fire Center (WFIGS)", "url": "https://data-nifc.opendata.arcgis.com/",
               "licence": "No licence stated (not verified); US interagency incident data, credited", "grade": "A2",
               "independence_group": "nifc", "source_type": "official incident report",
               "descriptor": "Wildfire incident: size, containment, county and state"}
NEIC = "NEIC"        # USGS's National Earthquake Information Center: an EMSC event carrying its solution is not independent
FIRE_ACRES_MIN = 100  # a wildfire needs this size to get a feed item (the map shows every one)
FIRE_MIN = 10  # a country needs this many detections in 24 hours to get a feed item (the map shows every cell)
FIRE_BASE_DAYS = 28  # a country's fire baseline: the median of its daily detections over the past 28 complete UTC days
FIRE_BASE_MIN = 14   # routine until the baseline holds this many days
FIRE_MULT = 3        # anomaly at 3 times the baseline median...
FIRE_FLOOR = 50      # ...and at least this many detections in 24 hours
FIRE_KEEP = 5  # a country item already open in the history state stays while it has this many, so it does not
               # end and reopen each time its count crosses FIRE_MIN
TSUNAMI_WORDS = {"information": "information statement", "threat": "threat message", "watch": "watch",
                 "advisory": "advisory", "warning": "warning"}
MONTHS3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _day(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MONTHS3[int(m) - 1]} {y}"


def _tidy_place(s: str) -> str:
    s = " ".join((s or "").split())
    return s.title() if s.isupper() else s


def _tsunami_items(d: dict, now: datetime) -> list[dict]:
    """Messages from the last 7 days, one per centre and earthquake. Anything above an information statement is an
    anomaly against the warning centres' own scale."""
    from .tsunami import CENTRE_NAMES, SHOW_DAYS
    out = []
    f = (d.get("tsunami") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    since = (now - timedelta(days=SHOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in (d.get("tsunami") or {}).get("records") or []:
        if (r.get("sent") or "") < since:
            continue
        hot = r["level"] != "information"
        mag = f"preliminary M{r['magnitude']:.1f} " if r.get("magnitude") is not None else ""
        place = _tidy_place(r.get("location"))
        late = None
        if r.get("origin") and r.get("sent"):
            gap = (datetime.fromisoformat(r["sent"].replace("Z", "+00:00"))
                   - datetime.fromisoformat(r["origin"].replace("Z", "+00:00"))).total_seconds() / 3600
            if gap > 6:
                late = f"The message gives an origin {gap:.0f} hours before it was sent; the centre's date may be wrong."
        p = {**_base(f), "id": f"elements:tsunami:{r['id']}",
             "title": f"Tsunami {TSUNAMI_WORDS.get(r['level'], r['level'])} ({r['centre']}): {mag}{place}".strip(),
             "tier": "anomaly" if hot else "routine", "data_as_of": r.get("sent") or f, "countries": r.get("countries") or [],
             "requirement_ids": ["EL-PIR-8"], "sources": [{**SRC["tsunami"], "url": r.get("url") or SRC["tsunami"]["url"], "accessed_at": f}],
             "link": r.get("url"),
             "measures": {"centre": CENTRE_NAMES.get(r["centre"], r["centre"]), "event": r.get("event"), "level": r["level"],
                          "message_type": r.get("msg_type"), "severity": r.get("severity"), "headline": r.get("headline"),
                          "location": place, "magnitude": r.get("magnitude"), "magnitude_type": r.get("magnitude_type"),
                          "origin": r.get("origin"), "depth_km": r.get("depth_km"), "origin_note": late}}
        if hot:
            p["baseline_ref"] = {"id": "tsunami-message-levels", "type": "fixed", "version": "1",
                                 "window": "NOAA tsunami messages: information statement, threat message, watch, advisory, warning"}
        g = _pt(r.get("lon"), r.get("lat"))
        if g is None:
            p.update({"precision_class": "none", "visual": {"type": "page", "url": r.get("url") or SRC["tsunami"]["url"]}})
        out.append({"type": "Feature", "geometry": g, "properties": p})
    return out


def _wildfire_items(d: dict, now: datetime) -> list[dict]:
    """NIFC wildfires of 100 acres or more that are still being fought or are new."""
    out = []
    f = (d.get("nifc") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for w in (d.get("nifc") or {}).get("records") or []:
        if w["acres"] < FIRE_ACRES_MIN:
            continue
        name = w["name"] if w["name"].lower().endswith(("fire", "complex")) else f"{w['name']} Fire"
        where = ", ".join(x for x in (f"{w['county']} County" if w.get("county") else None, w.get("state")) if x)
        held = f"{w['contained']}% contained" if w.get("contained") is not None else "containment not reported"
        p = {**_base(f), "id": f"elements:nifc:{(w['id'] or '').strip('{}').lower()}",
             "title": f"{name}, {where}: {w['acres']:,.0f} acres, {held} (NIFC)",
             "tier": "routine", "data_as_of": w.get("updated") or w.get("discovered") or f, "countries": ["US"],
             "requirement_ids": ["EL-PIR-10"], "sources": [{**SRC["nifc"], "accessed_at": f}], "link": SRC["nifc"]["url"],
             "measures": {"name": w["name"], "acres": w["acres"], "percent_contained": w.get("contained"),
                          "discovered": w.get("discovered"), "state": w.get("state"), "county": w.get("county"),
                          "cause": w.get("cause"), "complexity": w.get("complexity")}}
        out.append({"type": "Feature", "geometry": _pt(w["lon"], w["lat"]), "properties": p})
    return out


USDM_NEXT_DAYS = 9     # a map dated Tuesday is released that Thursday; the next one, nine days after its date
USDM_MARGIN_DAYS = 2   # a late release (a holiday week) before the reading counts as out of date


def usdm_valid_until(map_date: str) -> str:
    """The Drought Monitor's own valid period ends the Monday after its map date, three days before the next map is
    released, so a reading valid only to then sat on the feed past its end every week (24 Nov 2026: valid_until
    23 Nov, still current 16 h later). The reading stands until the next scheduled release plus a margin."""
    day = datetime.strptime(map_date, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
    return (day + timedelta(days=USDM_NEXT_DAYS + USDM_MARGIN_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _drought_item(d: dict, now: datetime) -> list[dict]:
    rec = (d.get("usdm") or {}).get("records") or {}
    weeks = rec.get("weeks") or [] if isinstance(rec, dict) else []
    if not weeks:
        return []
    w, prev = weeks[0], (weeks[1] if len(weeks) > 1 else None)
    f = (d.get("usdm") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lp = country_point("US")
    p = {**_base(f), "id": "elements:usdm:us",
         "title": (f"US Drought Monitor, week of {_day(w['map_date'])}: {w['d1']:.1f}% of the US in drought, "
                   f"{w['d2']:.1f}% severe or worse"),
         "tier": "routine", "data_as_of": f"{w['map_date']}T12:00:00Z", "valid_until": usdm_valid_until(w["map_date"]),
         "countries": ["US"], "precision_class": "country", "requirement_ids": ["EL-PIR-9"],
         "sources": [{**SRC["usdm"], "accessed_at": f}], "link": SRC["usdm"]["url"],
         "measures": {"map_date": w["map_date"], "valid_end": w.get("valid_end"), "cumulative_percent_area": True,
                      **{k: w[k] for k in ("d0", "d1", "d2", "d3", "d4")},
                      "previous_week": {k: prev[k] for k in ("map_date", "d0", "d1", "d2", "d3", "d4")} if prev else None,
                      "change_d1": round(w["d1"] - prev["d1"], 2) if prev else None,
                      "change_d2": round(w["d2"] - prev["d2"], 2) if prev else None}}
    if p["valid_until"] < now.strftime("%Y-%m-%dT%H:%M:%SZ"):
        return []   # no newer map by the next release and its margin: the reading has ended (the history keeps it)
    return [{"type": "Feature", "geometry": _pt(lp[1], lp[0]) if lp else None, "properties": p}]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_") or "unknown"


TERRITORIES = {"PR", "GU", "VI", "AS", "MP"}  # their own ISO country codes, not US states


@cache
def _county_states() -> dict:
    """County FIPS (SSCCC) -> USPS state code, from catalog/us_counties.json (Census 2025 Gazetteer)."""
    doc = json.loads((ROOT / "catalog" / "us_counties.json").read_text(encoding="utf-8"))
    return {k: v[3] for k, v in doc["counties"].items()}


def subdivide(feats: list[dict]) -> None:
    """Add `subdivisions` (kit 0.5.7, ISO 3166-2 codes such as US-HI) to US items, so consumers can tell a hazard in
    Hawaii from one for all of the US (15 Nov 2026). From NWS's own county codes when the item lists them, else
    from the item's point or shape on the kit's 1:10m state outlines (right to about 1 km at a state line). An item
    for the whole country (precision country, at the label point) gets none."""
    states = _county_states()
    for x in feats:
        p = x["properties"]
        if "US" not in (p.get("countries") or []) or p.get("subdivisions"):
            continue
        subs = {f"US-{states[c]}" for c in (p.get("measures") or {}).get("counties") or []
                if c in states and states[c] not in TERRITORIES}
        if not subs and p.get("precision_class") not in ("country", "none") and x.get("geometry"):
            subs = set(geo.subdivisions_for_geometry(x["geometry"]))
        if subs:
            p["subdivisions"] = sorted(subs)


def _volcano_items(d: dict, now: datetime) -> list[dict]:
    """USGS elevated volcanoes, each measured against NORMAL. An anomaly only when it matters as news (15 Nov
    2026: a standing or lowered alert is not one): the alert was raised, it is newly elevated, USGS gives no earlier
    level to compare with, or it stands at WARNING or aviation code RED (an eruption under way). A re-sent or
    lowered alert below WARNING is routine. The response_stage needs the kit's usgs_volcano
    ladder (kit 0.3.2); with an older kit, or for UNASSIGNED (no ground-based alert level, which the ladder has no rung
    for), the items go out without it."""
    from .volcanoes import change
    rungs = (vocab.ladders().get("usgs_volcano") or {}).get("values") or {}
    out = []
    f = (d.get("usgs_volcano") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for v in (d.get("usgs_volcano") or {}).get("records") or []:
        if not v.get("alert"):
            continue
        moved = change(v)
        prev = f"{(v.get('prev_alert') or '').title()}/{(v.get('prev_color') or '').title()}"
        was = ("previously unassigned" if (v.get("prev_alert") or "UNASSIGNED") == "UNASSIGNED"
               else f"{moved} from {prev}" if moved else None)
        ground = ("no ground-based alert level" if v["alert"] == "UNASSIGNED" else f"USGS volcano alert {v['alert'].title()}")
        title = (f"{v['name']}: {ground}, aviation code {(v.get('color') or 'none').title()}"
                 + (f" ({was})" if was else ""))
        known = bool(v.get("prev_alert") or v.get("prev_color"))
        top = v["alert"] == "WARNING" or (v.get("color") or "").upper() == "RED"
        news = top or moved == "raised" or not known
        p = {**_base(f), "id": f"elements:usgs-volcano:{v['vnum'] or _slug(v['name'])}", "title": title,
             "tier": "anomaly" if news else "routine", "data_as_of": v.get("sent") or f, "countries": v["countries"],
             "requirement_ids": ["EL-PIR-6"],
             "baseline_ref": {"id": "usgs-volcano-normal", "type": "fixed", "version": "1",
                              "window": "USGS volcano alert levels: NORMAL, ADVISORY, WATCH, WARNING (NORMAL is background)"},
             "sources": [{**SRC["usgs_volcano"], "url": v.get("url") or "https://volcanoes.usgs.gov/", "accessed_at": f}],
             "link": v.get("url"),
             "measures": {"name": v["name"], "vnum": v["vnum"], "alert_level": v["alert"], "aviation_color": v.get("color"),
                          "previous_alert_level": v.get("prev_alert"), "previous_aviation_color": v.get("prev_color"),
                          "change": moved, "changed_at": v.get("changed"), "observatory": v.get("observatory_name"), "nvews_threat": v.get("threat"),
                          "synopsis": v.get("synopsis")}}
        if v["alert"].lower() in rungs:
            p["response_stage"] = f"usgs_volcano:{v['alert'].lower()}"
        out.append({"type": "Feature", "geometry": _pt(v.get("lon"), v.get("lat")), "properties": p})
    return out


def _area_text(areas: list[str], limit: int = 80) -> str:
    text = "; ".join(areas)
    if len(text) <= limit:
        return text
    cut = text[:limit - 12].rsplit(";", 1)[0]
    return f"{cut} and {len(areas) - cut.count(';') - 1} more areas"


def _weather_items(d: dict, now: datetime) -> list[dict]:
    """NWS Severe and Extreme alerts (Extreme is an anomaly against the CAP severity scale) and SPC Day 1 risk areas
    (Moderate and High are anomalies against SPC's categorical scale). Neither scale is a kit ladder yet, so these
    items carry no response_stage."""
    from .weather import SPC_PAGE
    out = []
    f = (d.get("nws") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for e in (d.get("nws") or {}).get("records") or []:
        p = {**_base(f), "id": f"elements:nws:{e['id']}",
             "title": f"{e['event']} for {_area_text(e['areas'])} ({e['sender']})",
             "tier": "anomaly" if e["severity"] == "Extreme" else "routine", "data_as_of": e.get("sent") or f,
             "valid_until": e.get("ends"), "countries": e["countries"], "requirement_ids": ["EL-PIR-7"],
             "sources": [{**SRC["nws"], "url": e.get("url") or SRC["nws"]["url"], "accessed_at": f}], "link": e.get("url"),
             "measures": {"event": e["event"], "severity": e["severity"], "urgency": e.get("urgency"),
                          "certainty": e.get("certainty"), "office": e.get("sender"), "areas": e["areas"],
                          "counties": e["counties"], "onset": e.get("onset"), "ends": e.get("ends"), "vtec": e["id"]}}
        if e["severity"] == "Extreme":
            p["baseline_ref"] = {"id": "cap-severity", "type": "fixed", "version": "1",
                                 "window": "CAP severity: Minor, Moderate, Severe, Extreme"}
        if e.get("geometry"):
            g, p["precision_class"] = e["geometry"], "area"
        elif e.get("points"):
            g = {"type": "MultiPoint", "coordinates": e["points"]}
            p["precision_class"] = "approximate"   # each county's Census internal point
        else:
            g = None
            p.update({"precision_class": "none", "visual": {"type": "page", "url": e.get("url") or SRC["nws"]["url"]}})
        out.append({"type": "Feature", "geometry": g, "properties": p})
    f = (d.get("spc") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in (d.get("spc") or {}).get("records") or []:
        hot = r["level"] >= 4
        p = {**_base(f), "id": f"elements:spc:day1:{r['label'].lower()}",
             "title": f"SPC Day 1 convective outlook: {r['name']} (level {r['level']} of 5)",
             "tier": "anomaly" if hot else "routine", "data_as_of": r.get("issued") or f, "valid_until": r.get("expires"),
             "countries": ["US"], "requirement_ids": ["EL-PIR-7"], "precision_class": "area",
             "sources": [{**SRC["spc"], "url": SPC_PAGE, "accessed_at": f}], "link": SPC_PAGE,
             "measures": {"category": r["label"], "name": r["name"], "level": r["level"], "valid": r.get("valid"),
                          "expires": r.get("expires"), "fill": r.get("fill")}}
        if hot:
            p["baseline_ref"] = {"id": "spc-categorical", "type": "fixed", "version": "1",
                                 "window": "SPC categorical risk: Marginal, Slight, Enhanced, Moderate, High"}
        out.append({"type": "Feature", "geometry": r.get("geometry"), "properties": p})
    return out


def _meteoalarm_items(d: dict, now: datetime) -> list[dict]:
    """European warnings (MeteoAlarm). One item per orange or red warning, placed by its own polygon or its regions'
    points; red (very dangerous) is an anomaly against MeteoAlarm's awareness levels, as Extreme is for NWS. Yellow
    warnings, hundreds on an ordinary day, are counted in one item per country; every level is on the map
    (meteoalarm.json). Not a kit ladder yet, so no response_stage."""
    from .meteoalarm import PAGE
    out = []
    f = (d.get("meteoalarm") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    live = [r for r in (d.get("meteoalarm") or {}).get("records") or [] if (r.get("expires") or "") > stamp]
    for r in live:
        if r["level"] < 3:
            continue
        red = r["level"] == 4
        src = {**SRC["meteoalarm"], "publisher": f"{r['sender'] or 'National weather service'} via MeteoAlarm (EUMETNET)",
               "url": r.get("web") or PAGE, "accessed_at": f}
        p = {**_base(f), "id": f"elements:meteoalarm:{r['country'].lower()}:{r['id']}",
             "title": f"{r['colour'].title()} {r['type']} warning for {_area_text(r['areas'])} ({r['sender']})",
             "tier": "anomaly" if red else "routine", "data_as_of": r.get("sent") or f, "valid_until": r["expires"],
             "countries": [r["country"]], "requirement_ids": ["EL-PIR-11"], "sources": [src], "link": r.get("web") or PAGE,
             "precision_class": r["precision"],
             "measures": {"awareness_level": r["colour"], "level": r["level"], "awareness_type": r["type"],
                          "event": r.get("event"), "headline": r.get("headline"), "issuer": r["sender"],
                          "severity": r.get("severity"), "urgency": r.get("urgency"), "certainty": r.get("certainty"),
                          "onset": r.get("onset"), "expires": r["expires"], "areas": r["areas"], "placed": r.get("placed"),
                          "credit": r.get("credit"), "cap_identifier": r.get("identifier")}}
        if red:
            p["baseline_ref"] = {"id": "meteoalarm-awareness", "type": "fixed", "version": "1",
                                 "window": "MeteoAlarm awareness levels: green, yellow, orange, red (very dangerous)"}
        if r.get("polygons"):
            g = {"type": "MultiPolygon", "coordinates": r["polygons"]}
        elif r.get("points"):
            g = {"type": "MultiPoint", "coordinates": r["points"]}
        else:
            g = None
            p.update({"precision_class": "none", "visual": {"type": "page", "url": r.get("web") or PAGE}})
        out.append({"type": "Feature", "geometry": g, "properties": p})
    by_cc = {}
    for r in live:
        by_cc.setdefault(r["country"], []).append(r)
    for cc, rs in sorted(by_cc.items()):
        n = {c: sum(1 for r in rs if r["colour"] == c) for c in ("yellow", "orange", "red")}
        kinds = {}
        for r in rs:
            kinds[r["type"]] = kinds.get(r["type"], 0) + 1
        top = sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))
        name = country_name(cc)
        lp = country_point(cc)
        counts = ", ".join(f"{n[c]} {c}" for c in ("red", "orange", "yellow") if n[c])
        p = {**_base(f), "id": f"elements:meteoalarm:{cc.lower()}:in-force",
             "title": f"{len(rs)} weather warning{'s' if len(rs) != 1 else ''} in force in {name} ({counts}), most for "
                      f"{top[0][0]} (MeteoAlarm)",
             "tier": "routine", "data_as_of": max(r.get("sent") or f for r in rs), "countries": [cc],
             "precision_class": "country", "requirement_ids": ["EL-PIR-11"],
             "sources": [{**SRC["meteoalarm"], "url": PAGE, "accessed_at": f}], "link": PAGE,
             "measures": {"country_name": name, "warnings": len(rs), **n, "by_type": dict(top),
                          "issuers": sorted({r["sender"] for r in rs if r["sender"]}),
                          "note": "Every warning not yet expired, including those that start later; green messages are not counted"}}
        if lp:
            out.append({"type": "Feature", "geometry": _pt(lp[1], lp[0]), "properties": p})
        else:
            p.update({"precision_class": "none", "visual": {"type": "page", "url": PAGE}})
            out.append({"type": "Feature", "geometry": None, "properties": p})
    return out


PAGER_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
TC_NAMES = {"TD": "Tropical depression", "TS": "Tropical storm", "HU": "Hurricane", "STD": "Subtropical depression",
            "STS": "Subtropical storm", "PTC": "Potential tropical cyclone", "PT": "Post-tropical cyclone"}


def _not_after(when: str, limit: str) -> str:
    """when, or limit if when is later. GDACS gives a running flood or drought a todate in the future (the next day's
    01:00) and no time of its latest report, and data cannot be newer than the fetch that read them. Measured 14 Nov
    2026: every Elements item COP's archive showed dated after its snapshot (3, 6, 11 and 12 Nov; 1.6 to 5.5 h) was a
    GDACS flood, which is why Elements read "fresh" with a clock 1.6 h ahead on 12 Nov. The event's own from and to
    stay in measures."""
    def t(s):
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    try:
        return limit if t(when) > t(limit) else when
    except (TypeError, ValueError):
        return when


GDACS_GRACE_DAYS = 7


def gdacs_ended(e: dict, now: datetime) -> bool:
    """GDACS marks an event that has ended `iscurrent` false; the 14-day query returns it until it ages out, so it is
    not a current hazard. A current event whose latest report (its `to`) is more than GDACS_GRACE_DAYS old counts as
    ended too: GDACS's current events are re-reported every day or so (measured 26 Nov 2026: the oldest `to` among the
    11 current events was 3.9 days back, a cyclone's last advisory). `now` is the time of the read that returned the
    event (build passes it): while the lane fails, the copy's events are not aged out on the clock alone."""
    if not e.get("current"):
        return True
    try:
        to = datetime.fromisoformat(str(e.get("to")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return to + timedelta(days=GDACS_GRACE_DAYS) < now


def gdacs_valid_until(e: dict) -> str | None:
    """An ended event is valid until GDACS's own `to`; a current one until `to` plus the grace, when Elements would
    end it if GDACS sent no later report."""
    try:
        to = datetime.fromisoformat(str(e.get("to")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if e.get("current"):
        to += timedelta(days=GDACS_GRACE_DAYS)
    return to.strftime("%Y-%m-%dT%H:%M:%SZ")


def _base(fetched):
    return {"contract": CONTRACT, "program": "elements", "kind": "observation", "status": "actual", "msg_type": "new",
            "human_review": "none", "us_person_data": "none", "status_class": "reported", "method_version": METHOD,
            "product_category": "current", "published_at": fetched, "precision_class": "point",
            "ie_aspect": ["physical"], "pmesii_pt": ["physical_environment"], "ascope": ["events"]}


def _pt(lon, lat):
    return {"type": "Point", "coordinates": [lon, lat]} if lon is not None and lat is not None else None


US_STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
             "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
             "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
             "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
             "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
             "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
             "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
             "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
             "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"}
PLACE_ALIASES = {"Burma (Myanmar)": "MM", "Myanmar": "MM", "U.S. Virgin Islands": "VI", "Puerto Rico": "PR",
                 "Congo": "CG", "Democratic Republic of the Congo": "CD", "Timor Leste": "TL", "Timor-Leste": "TL",
                 "Turkey": "TR", "Türkiye": "TR", "Czech Republic": "CZ", "North Macedonia": "MK", "Eswatini": "SZ"}
TOWN_PLACE = re.compile(r"^\d+(?:\.\d+)? km [NSEW]{1,3} of .+, ([^,]+)$")


@cache
def _name_codes() -> dict:
    return {v: k for k, v in geo._names().items()} | {"United States": "US"}


def town_country(place: str | None, lon: float | None = None) -> str | None:
    """The ISO code of the country USGS's place text names after its reference town ("85 km S of Gorontalo,
    Indonesia" -> ID; a US state -> US), or None for a region name ("Fiji region") or a name not matched. The town is
    the one USGS chose to describe the location, not a measured nearest coast. A name that is both a US state and a
    country ("Georgia") is read by the epicentre's longitude: the state west of the prime meridian, the country east
    of it, and None when lon is not given."""
    m = TOWN_PLACE.match((place or "").strip())
    if not m:
        return None
    name = m.group(1).strip()
    country = PLACE_ALIASES.get(name) or _name_codes().get(name)
    if name in US_STATES:
        if not country:
            return "US"
        if lon is None:
            return None
        return "US" if lon < 0 else country
    return country


def fire_baseline(days: dict, cc: str, today: str) -> dict | None:
    """The country's baseline from data/firms_daily.json: the median of its detections over the past FIRE_BASE_DAYS
    complete UTC days before today (a day the file holds without the country counts 0), or None under
    FIRE_BASE_MIN days."""
    prior = sorted(k for k in days if k < today)[-FIRE_BASE_DAYS:]
    if len(prior) < FIRE_BASE_MIN:
        return None
    v = sorted((days[k] or {}).get(cc, 0) for k in prior)
    m = len(v) // 2
    med = v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2
    return {"median": med, "n": len(prior), "start": prior[0], "end": prior[-1]}


def build(d: dict, now: datetime | None = None, state: dict | None = None, since: str | None = None,
          ended: list | None = None, open_ids: set | None = None) -> dict:
    """d: {'usgs': {...records, fetched_at}, 'gdacs': ..., 'nhc': ..., 'cems': ...}. state and since: the history
    state after this run's history step and the log's first run, to fill last_change (contract revision 2.1).
    ended: a list to receive the GDACS events that have ended (gdacs_ended), built like feed items; they are not in
    the feed, and the history step keeps them as the last version of the items they end.
    open_ids: the item keys open in the history state (default: state's), for the FIRMS floor's hysteresis."""
    now = now or datetime.now(timezone.utc)
    feats = []
    from .emsc import match
    f = d["usgs"].get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    fe = (d.get("emsc") or {}).get("fetched_at") or f
    usgs_recs, emsc_recs = d["usgs"].get("records") or [], (d.get("emsc") or {}).get("records") or []
    pairs = match(usgs_recs, emsc_recs)
    for q in usgs_recs:
        alert = q.get("alert")
        hot = alert and PAGER_RANK.get(alert, 0) >= 1
        p = {**_base(f), "id": f"elements:usgs:{q['id']}", "title": f"M{q['mag']} earthquake, {q['place']}".rstrip(", "),
             "tier": "anomaly" if hot else "routine", "data_as_of": q["time"] or f, "countries": q["countries"],
             "requirement_ids": ["EL-PIR-1"], "sources": [{**SRC["usgs"], "url": q.get("url"), "accessed_at": f}],
             "link": q.get("url"), "measures": {"magnitude": q["mag"], "place": q["place"], "depth_km": q.get("depth_km"), "pager": alert,
                                                "tsunami_flag": q.get("tsunami"), "significance": q.get("sig")}}
        if alert:
            p["response_stage"] = f"pager:{alert}"
        if not q["countries"]:
            tc = town_country(q.get("place"), q.get("lon"))
            if tc:
                p["measures"]["town_country"] = tc       # a hint for an offshore quake; countries stays empty
        if hot:
            p["baseline_ref"] = {"id": "pager-green", "window": "USGS PAGER alert scale (green: little or no impact)",
                                 "type": "fixed", "version": "1"}
        e = pairs.get(q["id"])
        if e:
            independent = (e.get("authority") or "").upper() != NEIC
            p["measures"]["emsc"] = {"magnitude": e["mag"], "magnitude_type": e.get("magtype"), "authority": e.get("authority"),
                                     "independent": independent, "id": e["id"]}
            if independent:   # a second, independent catalogue reports the same earthquake
                p["sources"].append({**SRC["emsc"], "url": e["url"], "accessed_at": fe})
                c = rev21.corroboration(q, e)
                if c and c["corroborated_at"] > p["published_at"]:
                    c["corroborated_at"] = max(c["first_reported_at"], p["published_at"])
                if c and c["first_reported_at"] <= p["published_at"]:
                    p["corroboration"] = c
        feats.append({"type": "Feature", "geometry": _pt(q["lon"], q["lat"]), "properties": p})

    matched = {e["id"] for e in pairs.values()}
    for e in emsc_recs:
        if e["id"] in matched or (e.get("authority") or "").upper() == NEIC:
            continue   # a NEIC solution is USGS's own; USGS's feed carries it
        p = {**_base(fe), "id": f"elements:emsc:{e['id']}", "title": f"M{e['mag']} earthquake, {e['region']} (EMSC)",
             "tier": "routine", "data_as_of": e.get("time") or fe, "countries": e["countries"], "requirement_ids": ["EL-PIR-1"],
             "sources": [{**SRC["emsc"], "url": e["url"], "accessed_at": fe}], "link": e["url"],
             "measures": {"magnitude": e["mag"], "magnitude_type": e.get("magtype"), "place": e["region"],
                          "depth_km": e.get("depth_km"), "authority": e.get("authority"), "usgs_match": False}}
        feats.append({"type": "Feature", "geometry": _pt(e["lon"], e["lat"]), "properties": p})

    f = d["gdacs"].get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:   # ended-by-age is judged at the last good read: a failing lane's copy is not aged out on the clock alone
        read_at = min(now, datetime.fromisoformat(f.replace("Z", "+00:00")))
    except (TypeError, ValueError):
        read_at = now
    gone = []
    for e in d["gdacs"].get("records") or []:
        over = gdacs_ended(e, read_at)
        hot = e["alert"] in ("orange", "red") and not over
        name = e["name"] or e["kind"]
        if len(name) > 90:  # drought names list every country; the full list stays in countries
            name = name[:87].rsplit(",", 1)[0] + ", and others"
        sev = (e.get("severity") or "").strip() or None
        if e["type"] == "TC" and e.get("severity_value"):
            # GDACS pairs the storm's latest stage ("Tropical Depression") with the event's maximum wind; give the wind alone
            sev = f"maximum wind {round(e['severity_value'])} {e.get('severity_unit') or 'km/h'}"
        elif e["type"] == "FL" and not e.get("severity_value"):
            sev = None  # GDACS floods carry "Magnitude 0"
        elif sev:
            sev = re.sub(r"(\d{4,}) km2\b", lambda m: f"{int(m.group(1)):,} km²", sev)
        p = {**_base(f), "id": f"elements:gdacs:{e['id']}",
             "title": f"GDACS {e['alert'] or 'unrated'} alert: {name}" + (f" ({sev})" if sev else ""),
             "tier": "anomaly" if hot else "routine", "data_as_of": _not_after(e["to"] or e["from"] or f, f), "countries": e["countries"],
             "requirement_ids": ["EL-PIR-2"], "sources": [{**SRC["gdacs"], "url": e.get("report") or "https://www.gdacs.org/",
                                                           "accessed_at": f}],
             "link": e.get("report"), "measures": {"hazard": e["kind"], "hazard_code": e["type"], "name": e["name"],
                                                   "severity": sev, "alert_score": e.get("score"),
                                                   "latest_alert": e.get("latest_alert"), "current": e.get("current"),
                                                   "from": e["from"], "to": e["to"]}}
        if gdacs_valid_until(e):
            p["valid_until"] = gdacs_valid_until(e)
        if e["alert"] in ("green", "orange", "red"):
            p["response_stage"] = f"gdacs:{e['alert']}"
        if hot:
            p["baseline_ref"] = {"id": "gdacs-green", "window": "GDACS alert scale (green: low humanitarian impact)",
                                 "type": "fixed", "version": "1"}
        if over:
            p["measures"]["current"] = False
        (gone if over else feats).append({"type": "Feature", "geometry": _pt(e["lon"], e["lat"]), "properties": p})

    f = d["nhc"].get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for s in d["nhc"].get("records") or []:
        kind = TC_NAMES.get(s.get("classification"), s.get("classification") or "Tropical cyclone")
        p = {**_base(f), "id": f"elements:nhc:{s['id']}", "title": f"{kind} {s['name']}: {s.get('intensity_kt')} kt, {s.get('pressure_mb')} mb",
             "tier": "routine", "data_as_of": s.get("updated") or f, "countries": [], "requirement_ids": ["EL-PIR-3"],
             "sources": [{**SRC["nhc"], "accessed_at": f}], "link": s.get("advisory"),
             "measures": {"name": s.get("name"), "classification": s.get("classification"), "intensity_kt": s.get("intensity_kt"),
                          "pressure_mb": s.get("pressure_mb"), "movement": s.get("movement")}}
        feats.append({"type": "Feature", "geometry": _pt(s["lon"], s["lat"]), "properties": p})

    f = d["cems"].get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff = (now - timedelta(days=CEMS_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for a in d["cems"].get("records") or []:
        if (a.get("activated") or "") < cutoff and a.get("closed"):
            continue
        link = f"https://rapidmapping.emergency.copernicus.eu/{a['code']}/"
        p = {**_base(f), "id": f"elements:cems:{a['code']}", "title": f"Copernicus EMS {a['code']}: {a['name']}",
             "tier": "routine", "data_as_of": a.get("updated") or a.get("activated") or f, "countries": a["countries"],
             "response_stage": "cems:closed" if a.get("closed") else "cems:activated", "requirement_ids": ["EL-PIR-4"],
             "precision_class": "area", "sources": [{**SRC["cems"], "url": link, "accessed_at": f}], "link": link,
             "measures": {"code": a["code"], "name": a.get("name"), "category": a.get("category"), "event": a.get("event"), "activated": a.get("activated"),
                          "products": a.get("products"), "closed": a.get("closed")}}
        g = _pt(a.get("lon"), a.get("lat"))
        if g is None:
            p.update({"precision_class": "none", "visual": {"type": "page", "url": link}})
        feats.append({"type": "Feature", "geometry": g, "properties": p})

    feats += _volcano_items(d, now)
    feats += _weather_items(d, now)
    feats += _tsunami_items(d, now)
    feats += _drought_item(d, now)
    feats += _meteoalarm_items(d, now)
    feats += _wildfire_items(d, now)

    fp = (d.get("firms") or {}).get("records") or {}
    f = (d.get("firms") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    by_cc = {}
    for lon, lat, n, high, frp, mx, latest, cc in fp.get("cells") or []:
        if not cc:
            continue
        a = by_cc.setdefault(cc, {"n": 0, "high": 0, "frp": 0.0, "max": 0.0, "latest": "", "cells": 0, "sx": 0.0, "sy": 0.0})
        a["n"] += n
        a["high"] += high
        a["frp"] += frp
        a["max"] = max(a["max"], mx)
        a["latest"] = max(a["latest"], latest)
        a["cells"] += 1
        a["sx"] += lon * n
        a["sy"] += lat * n
    window = fp.get("window") or [None, None]
    if open_ids is None:
        open_ids = set((state or {}).get("open") or {})
    fire_days = (d.get("firms_daily") or {}).get("days") or {}
    today = now.strftime("%Y-%m-%d")
    for cc, a in sorted(by_cc.items()):
        if a["n"] < (FIRE_KEEP if f"elements:firms:{cc}" in open_ids else FIRE_MIN):
            continue
        name = country_name(cc)
        lp = country_point(cc)  # [lat, lon]; the detections' centre when the kit has no label point
        g = _pt(lp[1], lp[0]) if lp else _pt(round(a["sx"] / a["n"], 2), round(a["sy"] / a["n"], 2))
        p = {**_base(f), "id": f"elements:firms:{cc}",
             "title": f"{a['n']:,} fire and heat detections in {name}, past 24 hours (VIIRS)",
             "tier": "routine", "data_as_of": a["latest"].replace("Z", ":00Z"), "countries": [cc],
             "precision_class": "country", "requirement_ids": ["EL-PIR-5"],
             "sources": [{**SRC["firms"], "accessed_at": f}], "link": "https://firms.modaps.eosdis.nasa.gov/map/",
             "measures": {"country_name": name, "detections": a["n"], "high_confidence": a["high"],
                          "frp_sum_mw": round(a["frp"], 1), "frp_max_mw": round(a["max"], 1), "cells": a["cells"],
                          "cell_deg": fp.get("cell_deg"), "window_start": window[0], "window_end": window[1],
                          "note": "Detections, not fires: each overpass counts, and gas flares and other heat sources are included"}}
        base = fire_baseline(fire_days, cc, today)
        if base is not None:
            med = base["median"]
            p["measures"].update({"baseline_median": med, "baseline_days": base["n"]})
            p["baseline_ref"] = {"id": "firms-country-median", "type": "rolling", "version": "1",
                                 "window": f"median of daily detections, {base['start']} to {base['end']} "
                                           f"({base['n']} complete UTC days); anomaly at {FIRE_MULT} times the median "
                                           f"and at least {FIRE_FLOOR} detections"}
            if a["n"] >= FIRE_FLOOR and a["n"] >= FIRE_MULT * med:
                p["tier"] = "anomaly"
        feats.append({"type": "Feature", "geometry": g, "properties": p})

    subdivide(feats)
    rev21.finish(feats, state, since)
    if ended is not None and gone:
        subdivide(gone)
        rev21.finish(gone, state, since)
        ended.extend(gone)
    regs = registers.ids(ROOT / "doctrine")
    kept, dropped = [], []
    for x in feats:
        errs = [m for _, sev, m in contract.check(x, regs) if sev == "error"]
        (dropped.append({"id": x["properties"]["id"], "errors": errs}) if errs else kept.append(x))
    stamp = max([(d.get(k) or {}).get("fetched_at") or "" for k in ("usgs", "gdacs", "nhc", "cems", "firms", "usgs_volcano", "nws", "spc", "tsunami", "usdm", "meteoalarm", "emsc", "nifc")] + [""]) \
        or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    newest = {}
    for x in kept:
        p = x["properties"]
        k = (p.get("sources") or [{}])[0].get("id")
        if k and p.get("data_as_of") and p["data_as_of"] > newest.get(k, ""):
            newest[k] = p["data_as_of"]
    return {"type": "FeatureCollection", "contract": CONTRACT, "contract_rev": contract.CONTRACT_REV, "kit": KIT,
            "program": "elements", "generated_at": stamp,
            "licence": "Elements code GNU AGPL-3.0; USGS, NOAA and NASA content US public domain or open; GDACS and Copernicus content "
                       "with attribution; MeteoAlarm and EMSC content CC BY 4.0; US Drought Monitor and NIFC WFIGS state "
                       "no licence and are credited",
            "attribution": "Elements, The Intelligence Company. Sources: USGS, EMSC (European-Mediterranean Seismological Centre), "
                           "GDACS, NOAA NHC, Copernicus EMS (© European Union), "
                           "NASA FIRMS (LANCE, operated by NASA's Earth Science Data and Information System), "
                           "MeteoAlarm (EUMETNET) and the national weather services that issue its warnings, the US Drought "
                           "Monitor (NDMC University of Nebraska-Lincoln, USDA, NOAA) and the National Interagency Fire "
                           "Center (WFIGS).",
            "language_key": "https://github.com/metacog-osint/tic-doctrine/blob/main/docs/language-key.md",
            # The kit's per-source health block, keyed by the source id each item carries (15 Nov 2026): COP's ledger
            # reads it so that a failed source's kept items neither end nor count as seen again.
            "health": rev21.health_states(d.get("health") or {}, newest, now),
            "dropped": dropped, "features": kept}
