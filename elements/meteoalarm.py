"""European weather warnings from MeteoAlarm (EUMETNET), CC BY 4.0.

MeteoAlarm gathers the official warnings of 39 national weather services (the EU, the UK, Norway, Switzerland, the
Balkans, Ukraine, Moldova and Israel) and publishes them as CAP 1.2, one JSON file per country, open and without a key
(feeds.meteoalarm.org/api/v1/warnings/feeds-{country}). Each warning carries MeteoAlarm's awareness level (green,
yellow, orange, red: no particular awareness, potentially dangerous, dangerous, very dangerous) and type (wind, rain,
thunderstorm and so on).

- Kept: actual, public warnings at yellow, orange or red that have not expired. Green messages ("no particular
  awareness") and all-clear updates are dropped. Each warning has one English text block, which is the one read.
- The files already leave out messages that a later update replaced. A warning keeps one id across its updates: the
  identifier of the first message in its chain of references.
- Places: a warning area drawn as a polygon keeps it. Otherwise the area is placed at its region's point
  (catalog/meteoalarm_areas.json, one point per MeteoAlarm region, from MeteoAlarm's geocodes file) by region code,
  then by region name within the country (France names its departments by NUTS3 code only), and failing both at the
  country's label point.
- A country whose file fails keeps its earlier warnings until they expire."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache

from .common import ROOT, country_point, fetch_or_none, to_utc

URL = "https://feeds.meteoalarm.org/api/v1/warnings/feeds-{feed}"
PAGE = "https://meteoalarm.org/en/live/"
# MeteoAlarm's feed name -> ISO 3166-1 alpha-2 (feeds.meteoalarm.org lists these 39, 5 Nov 2026)
FEEDS = {"andorra": "AD", "austria": "AT", "belgium": "BE", "bosnia-herzegovina": "BA", "bulgaria": "BG",
         "croatia": "HR", "cyprus": "CY", "czechia": "CZ", "denmark": "DK", "estonia": "EE", "finland": "FI",
         "france": "FR", "germany": "DE", "greece": "GR", "hungary": "HU", "iceland": "IS", "ireland": "IE",
         "israel": "IL", "italy": "IT", "latvia": "LV", "lithuania": "LT", "luxembourg": "LU", "malta": "MT",
         "moldova": "MD", "montenegro": "ME", "netherlands": "NL", "norway": "NO", "poland": "PL", "portugal": "PT",
         "republic-of-north-macedonia": "MK", "romania": "RO", "serbia": "RS", "slovakia": "SK", "slovenia": "SI",
         "spain": "ES", "sweden": "SE", "switzerland": "CH", "ukraine": "UA", "united-kingdom": "GB"}
LEVELS = {2: "yellow", 3: "orange", 4: "red"}   # 1 is green: no particular awareness, not kept
TYPES = {1: "wind", 2: "snow or ice", 3: "thunderstorm", 4: "fog", 5: "high temperature", 6: "low temperature",
         7: "coastal event", 8: "forest fire", 9: "avalanche", 10: "rain", 12: "flooding", 13: "rain and flooding",
         14: "marine hazard", 15: "drought"}   # MeteoAlarm CAP profile v2.0 awareness types
MAX_BYTES = 24 * 1024 * 1024   # Israel's file was 5.1 MB on 5 Nov 2026
WORKERS = 6


# ---- geometry ----------------------------------------------------------------------------------------------------
def _ring_area_centroid(ring):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        k = x0 * y1 - x1 * y0
        a += k
        cx += (x0 + x1) * k
        cy += (y0 + y1) * k
    if abs(a) < 1e-12:
        return 0.0, sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    return a / 2, cx / (3 * a), cy / (3 * a)


def _inside(x, y, ring):
    hit = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def rep_point(polygons):
    """A point inside the largest polygon: its centroid when that falls inside, otherwise the middle of the widest
    stretch of the polygon along the centroid's latitude. polygons: [[outer ring, hole, ...], ...], rings as
    [[lon, lat], ...]. Returns [lon, lat] rounded to 3 decimals, or None."""
    best = None
    for rings in polygons or []:
        if not rings or len(rings[0]) < 3:
            continue
        area, cx, cy = _ring_area_centroid(rings[0])
        if best is None or abs(area) > best[0]:
            best = (abs(area), cx, cy, rings)
    if best is None:
        return None
    _, cx, cy, rings = best

    def ok(x, y):
        return _inside(x, y, rings[0]) and not any(_inside(x, y, h) for h in rings[1:])

    cands = [(cx, cy)]
    xs = sorted(x0 + (cy - y0) * (x1 - x0) / (y1 - y0)
                for ring in rings for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]) if (y0 > cy) != (y1 > cy))
    spans = [(xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2) for i in range(0, len(xs) - 1, 2)]
    if spans:
        cands.append((max(spans)[1], cy))
    for x, y in cands:   # checked after rounding: a centroid on the edge can round to just outside
        if ok(round(x, 3), round(y, 3)):
            return [round(x, 3), round(y, 3)]
    x, y = cands[-1] if spans else rings[0][0]
    return [round(x, 5), round(y, 5)]


def parse_polygon(text: str):
    """A CAP polygon ("lat,lon lat,lon ...") as a closed ring [[lon, lat], ...], or None."""
    pts = []
    for pair in (text or "").split():
        try:
            lat, lon = (float(v) for v in pair.split(","))
        except ValueError:
            return None
        pts.append([round(lon, 3), round(lat, 3)])
    if len(pts) < 3:
        return None
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _norm(name: str) -> str:
    """'Corse-du-Sud' and 'Corse du Sud', 'Val-d’Oise' and "Val-d'Oise", match."""
    return " ".join((name or "").lower().replace("’", "'").replace("-", " ").replace("_", " ").split())


@lru_cache(maxsize=1)
def areas() -> tuple[dict, dict]:
    """(by region code, by (country, normalised name)) from catalog/meteoalarm_areas.json."""
    p = ROOT / "catalog" / "meteoalarm_areas.json"
    table = json.loads(p.read_text(encoding="utf-8"))["areas"] if p.exists() else {}
    names = {}
    for code, (lat, lon, name, cc) in table.items():
        names.setdefault((cc, _norm(name)), code)
    return table, names


# ---- parsing -----------------------------------------------------------------------------------------------------
def _params(info) -> dict:
    return {p.get("valueName"): p.get("value") for p in info.get("parameter") or [] if isinstance(p, dict)}


def _number(text):
    """'2; yellow; Moderate' -> 2, '13; rain-flood' -> 13."""
    try:
        return int(str(text or "").split(";")[0].strip())
    except ValueError:
        return None


def _key(alert) -> str:
    """The first message in the warning's chain: references are 'sender,identifier,sent' separated by spaces."""
    refs = []
    for r in (alert.get("references") or "").split():
        parts = r.split(",")
        if len(parts) >= 3:
            refs.append((to_utc(parts[2]) or parts[2], parts[1]))
    return min(refs)[1] if refs else alert.get("identifier") or ""


def _place(info_areas, cc):
    """(polygons or None, points, precision, method per area)."""
    table, names = areas()
    polys, points, methods = [], [], []
    for a in info_areas:
        rings = [r for r in (parse_polygon(t) for t in a.get("polygon") or []) if r]
        if rings:
            polys += [[r] for r in rings]
            pt = rep_point([[r] for r in rings])
            methods.append("polygon")
        else:
            codes = [g.get("value") for g in a.get("geocode") or [] if g.get("valueName") == "EMMA_ID"]
            code = next((c for c in codes if c in table), None) or names.get((cc, _norm(a.get("areaDesc"))))
            if code:
                lat, lon = table[code][:2]
                pt, how = [lon, lat], "region"
            else:
                lp = country_point(cc)
                pt, how = ([round(lp[1], 3), round(lp[0], 3)] if lp else None), "country"
            methods.append(how)
        if pt and pt not in points:
            points.append(pt)
    if not info_areas:
        lp = country_point(cc)
        if lp:
            points.append([round(lp[1], 3), round(lp[0], 3)])
        methods.append("country")
    if methods and all(m == "polygon" for m in methods):
        return polys, points, "area", methods
    return None, points, ("country" if "country" in methods else "approximate"), methods


def parse(doc: dict, feed: str, now: datetime) -> list[dict]:
    cc = FEEDS.get(feed)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {}
    for w in doc.get("warnings") or []:
        a = (w or {}).get("alert") or {}
        if a.get("status") != "Actual" or a.get("scope", "Public") != "Public" or a.get("msgType") == "Cancel":
            continue
        infos = [i for i in a.get("info") or [] if isinstance(i, dict)]
        info = next((i for i in infos if (i.get("language") or "").lower().startswith("en")), infos[0] if infos else None)
        if info is None or "AllClear" in (info.get("responseType") or []):
            continue
        p = _params(info)
        level = _number(p.get("awareness_level"))
        expires = to_utc(info.get("expires"))
        if level not in LEVELS or not expires or expires <= stamp:
            continue
        kind = _number(p.get("awareness_type"))
        area_list = info.get("area") or next((i.get("area") for i in infos if i.get("area")), None) or []
        polys, points, precision, methods = _place(area_list, cc)
        credit = next((e.get("value") for e in info.get("eventCode") or [] if e.get("valueName") == "LICENSE"), None)
        rec = {"id": hashlib.sha1(_key(a).encode()).hexdigest()[:12], "identifier": a.get("identifier"),
               "feed": feed, "country": cc, "sender": " ".join((info.get("senderName") or "").split()),
               "event": info.get("event"), "headline": " ".join((info.get("headline") or "").split()),
               "level": level, "colour": LEVELS[level], "type_code": kind,
               "type": TYPES.get(kind, (p.get("awareness_type") or "").split(";")[-1].strip() or "weather"),
               "severity": info.get("severity"), "urgency": info.get("urgency"), "certainty": info.get("certainty"),
               "sent": to_utc(a.get("sent")), "onset": to_utc(info.get("onset") or info.get("effective")),
               "expires": expires, "web": info.get("web"), "credit": credit,
               "areas": [" ".join((x.get("areaDesc") or "").split()) for x in area_list],
               "placed": {m: methods.count(m) for m in sorted(set(methods))},
               "precision": precision, "points": points, "polygons": polys}
        prev = out.get(rec["id"])
        if not prev or (rec["sent"] or "") >= (prev["sent"] or ""):
            out[rec["id"]] = rec
    return list(out.values())


def collect(old, now: datetime | None = None, fetch=fetch_or_none, feeds=None):
    """(records, problem). Each country's file is fetched (a few at a time); a country that fails keeps its earlier
    warnings until they expire."""
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    feeds = list(feeds or FEEDS)

    def one(feed):
        body, err = fetch(URL.format(feed=feed), 60, MAX_BYTES)
        if body is None:
            return feed, None, err
        try:
            return feed, parse(json.loads(body), feed, now), None
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            return feed, None, f"parse: {type(e).__name__}"

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(one, feeds))
    kept, failed = [], []
    for feed, recs, err in results:
        if recs is None:
            failed.append(f"{feed}: {err}")
            kept += [r for r in old or [] if r.get("feed") == feed and (r.get("expires") or "") > stamp]
        else:
            kept += recs
    if failed and len(failed) == len(feeds) and not kept:
        return old or [], "every country failed: " + "; ".join(failed[:3])
    kept.sort(key=lambda r: (-r["level"], r["country"] or "", r["onset"] or "", r["id"]))
    return kept, (f"{len(failed)} of {len(feeds)} countries failed: " + "; ".join(failed[:5]) if failed else None)


def summary(records) -> str:
    n = {c: sum(1 for r in records or [] if r.get("colour") == c) for c in ("yellow", "orange", "red")}
    countries = len({r.get("country") for r in records or []})
    return (f"{len(records or [])} warnings in force in {countries} countries "
            f"(yellow {n['yellow']}, orange {n['orange']}, red {n['red']})")
