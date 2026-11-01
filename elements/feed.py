"""Elements' feed in contract v2 (tic-feed/2). Every item is a measurement (kind observation) of what an authority
published, with its own alert ladder as response_stage (pager:*, gdacs:*, cems:*). An alert above the bottom rung
(PAGER yellow or worse, GDACS orange or red) is an anomaly against that ladder's baseline. Each item passes the
doctrine kit's linter or is dropped and listed."""
import re
from datetime import datetime, timedelta, timezone

from .common import ROOT, country_name, country_point  # first: puts the doctrine kit on sys.path
from tic_doctrine import CONTRACT, contract, registers, vocab  # noqa: E402

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
    "firms": {"id": "nasa-firms", "publisher": "NASA FIRMS (LANCE, Earth Science Data and Information System)",
              "url": "https://firms.modaps.eosdis.nasa.gov/", "licence": "NASA open data, with acknowledgement of LANCE FIRMS",
              "grade": "A2", "independence_group": "nasa", "source_type": "satellite detection",
              "descriptor": "VIIRS active fire and thermal-anomaly detections (NOAA-20, NOAA-21, Suomi-NPP)"},
}
SRC["usgs_volcano"] = {"id": "usgs-volcanoes", "publisher": "USGS Volcano Hazards Program", "licence": "US public domain",
                       "grade": "A1", "independence_group": "usgs", "source_type": "official alert",
                       "descriptor": "Volcano alert level and aviation colour code from the responsible USGS observatory"}
FIRE_MIN = 10  # a country needs this many detections in 24 hours to get a feed item (the map shows every cell)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_") or "unknown"


def _volcano_items(d: dict, now: datetime) -> list[dict]:
    """USGS elevated volcanoes. Every one is an anomaly against NORMAL. The response_stage needs the kit's usgs_volcano
    ladder (kit 0.3.1); with an older kit the items go out without it."""
    from .volcanoes import change
    has_ladder = "usgs_volcano" in vocab.ladders()
    out = []
    f = (d.get("usgs_volcano") or {}).get("fetched_at") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for v in (d.get("usgs_volcano") or {}).get("records") or []:
        if not v.get("alert"):
            continue
        moved = change(v)
        prev = f"{(v.get('prev_alert') or '').title()}/{(v.get('prev_color') or '').title()}"
        was = ("previously unassigned" if (v.get("prev_alert") or "UNASSIGNED") == "UNASSIGNED"
               else f"{moved} from {prev}" if moved else None)
        title = (f"{v['name']}: USGS volcano alert {v['alert'].title()}, aviation code {(v.get('color') or 'none').title()}"
                 + (f" ({was})" if was else ""))
        p = {**_base(f), "id": f"elements:usgs-volcano:{v['vnum'] or _slug(v['name'])}", "title": title,
             "tier": "anomaly", "data_as_of": v.get("sent") or f, "countries": v["countries"],
             "requirement_ids": ["EL-PIR-6"],
             "baseline_ref": {"id": "usgs-volcano-normal", "type": "fixed", "version": "1",
                              "window": "USGS volcano alert levels: NORMAL, ADVISORY, WATCH, WARNING (NORMAL is background)"},
             "sources": [{**SRC["usgs_volcano"], "url": v.get("url") or "https://volcanoes.usgs.gov/", "accessed_at": f}],
             "link": v.get("url"),
             "measures": {"name": v["name"], "vnum": v["vnum"], "alert_level": v["alert"], "aviation_color": v.get("color"),
                          "previous_alert_level": v.get("prev_alert"), "previous_aviation_color": v.get("prev_color"),
                          "change": moved, "observatory": v.get("observatory_name"), "nvews_threat": v.get("threat"),
                          "synopsis": v.get("synopsis")}}
        if has_ladder:
            p["response_stage"] = f"usgs_volcano:{v['alert'].lower()}"
        out.append({"type": "Feature", "geometry": _pt(v.get("lon"), v.get("lat")), "properties": p})
    return out


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

    feats += _volcano_items(d, now)

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
    for cc, a in sorted(by_cc.items()):
        if a["n"] < FIRE_MIN:
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
        feats.append({"type": "Feature", "geometry": g, "properties": p})

    regs = registers.ids(ROOT / "doctrine")
    kept, dropped = [], []
    for x in feats:
        errs = [m for _, sev, m in contract.check(x, regs) if sev == "error"]
        (dropped.append({"id": x["properties"]["id"], "errors": errs}) if errs else kept.append(x))
    stamp = max([(d.get(k) or {}).get("fetched_at") or "" for k in ("usgs", "gdacs", "nhc", "cems", "firms", "usgs_volcano")] + [""]) \
        or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"type": "FeatureCollection", "contract": CONTRACT, "program": "elements", "generated_at": stamp,
            "licence": "Elements code MIT; USGS, NOAA and NASA content US public domain or open; GDACS and Copernicus content with attribution",
            "attribution": "Elements, The Intelligence Company. Sources: USGS, GDACS, NOAA NHC, Copernicus EMS (© European Union), "
                           "NASA FIRMS (LANCE, operated by NASA's Earth Science Data and Information System).",
            "language_key": "https://github.com/metacog-osint/tic-doctrine/blob/main/docs/language-key.md",
            "dropped": dropped, "features": kept}
