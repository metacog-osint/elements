"""Elements' feed in contract v2 (tic-feed/2). Every item is a measurement (kind observation) of what an authority
published, with its own alert ladder as response_stage (pager:*, gdacs:*, cems:*). An alert above the bottom rung
(PAGER yellow or worse, GDACS orange or red) is an anomaly against that ladder's baseline. Each item passes the
doctrine kit's linter or is dropped and listed."""
import re
from datetime import datetime, timedelta, timezone

from .common import ROOT  # first: puts the doctrine kit on sys.path
from tic_doctrine import CONTRACT, contract, registers  # noqa: E402

METHOD = "elements-feed-1.0"
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
}
PAGER_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
TC_NAMES = {"TD": "Tropical depression", "TS": "Tropical storm", "HU": "Hurricane", "STD": "Subtropical depression",
            "STS": "Subtropical storm", "PTC": "Potential tropical cyclone", "PT": "Post-tropical cyclone"}


def _base(fetched):
    return {"contract": CONTRACT, "program": "elements", "kind": "observation", "status": "actual", "msg_type": "new",
            "human_review": "none", "us_person_data": "none", "status_class": "reported", "method_version": METHOD,
            "product_category": "current", "published_at": fetched, "precision_class": "point",
            "ie_aspect": ["physical"], "pmesii_pt": ["physical_environment"], "ascope": ["events"]}


def _pt(lon, lat):
    return {"type": "Point", "coordinates": [lon, lat]} if lon is not None and lat is not None else None


def build(d: dict, now: datetime | None = None) -> dict:
    """d: {'usgs': {...records, fetched_at}, 'gdacs': ..., 'nhc': ..., 'cems': ...}"""
    now = now or datetime.now(timezone.utc)
    feats = []
    f = d["usgs"].get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for q in d["usgs"].get("records") or []:
        alert = q.get("alert")
        hot = alert and PAGER_RANK.get(alert, 0) >= 1
        p = {**_base(f), "id": f"elements:usgs:{q['id']}", "title": f"M{q['mag']} earthquake, {q['place']}".rstrip(", "),
             "tier": "anomaly" if hot else "routine", "data_as_of": q["time"] or f, "countries": q["countries"],
             "requirement_ids": ["EL-PIR-1"], "sources": [{**SRC["usgs"], "url": q.get("url"), "accessed_at": f}],
             "link": q.get("url"), "measures": {"magnitude": q["mag"], "place": q["place"], "depth_km": q.get("depth_km"), "pager": alert,
                                                "tsunami_flag": q.get("tsunami"), "significance": q.get("sig")}}
        if alert:
            p["response_stage"] = f"pager:{alert}"
        if hot:
            p["baseline_ref"] = {"id": "pager-green", "window": "USGS PAGER alert scale (green: little or no impact)",
                                 "type": "fixed", "version": "1"}
        feats.append({"type": "Feature", "geometry": _pt(q["lon"], q["lat"]), "properties": p})

    f = d["gdacs"].get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for e in d["gdacs"].get("records") or []:
        hot = e["alert"] in ("orange", "red")
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
             "tier": "anomaly" if hot else "routine", "data_as_of": e["to"] or e["from"] or f, "countries": e["countries"],
             "requirement_ids": ["EL-PIR-2"], "sources": [{**SRC["gdacs"], "url": e.get("report") or "https://www.gdacs.org/",
                                                           "accessed_at": f}],
             "link": e.get("report"), "measures": {"hazard": e["kind"], "hazard_code": e["type"], "name": e["name"],
                                                   "severity": sev, "alert_score": e.get("score"),
                                                   "latest_alert": e.get("latest_alert"), "current": e.get("current"),
                                                   "from": e["from"], "to": e["to"]}}
        if e["alert"] in ("green", "orange", "red"):
            p["response_stage"] = f"gdacs:{e['alert']}"
        if hot:
            p["baseline_ref"] = {"id": "gdacs-green", "window": "GDACS alert scale (green: low humanitarian impact)",
                                 "type": "fixed", "version": "1"}
        feats.append({"type": "Feature", "geometry": _pt(e["lon"], e["lat"]), "properties": p})

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

    regs = registers.ids(ROOT / "doctrine")
    kept, dropped = [], []
    for x in feats:
        errs = [m for _, sev, m in contract.check(x, regs) if sev == "error"]
        (dropped.append({"id": x["properties"]["id"], "errors": errs}) if errs else kept.append(x))
    stamp = max([d[k].get("fetched_at") or "" for k in ("usgs", "gdacs", "nhc", "cems")] + [""]) or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"type": "FeatureCollection", "contract": CONTRACT, "program": "elements", "generated_at": stamp,
            "licence": "Elements code MIT; USGS and NOAA content US public domain; GDACS and Copernicus content with attribution",
            "attribution": "Elements, The Intelligence Company. Sources: USGS, GDACS, NOAA NHC, Copernicus EMS (© European Union).",
            "language_key": "https://github.com/metacog-osint/tic-doctrine/blob/main/docs/language-key.md",
            "dropped": dropped, "features": kept}
