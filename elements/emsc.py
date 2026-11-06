"""EMSC earthquakes: the European-Mediterranean Seismological Centre's event service (seismicportal.eu FDSN), magnitude
4.5 and above, past 7 days. Data under Creative Commons Attribution 4.0 (CC BY 4.0).

EMSC is a second catalogue, independent of USGS. Each USGS earthquake that EMSC also reports (within 90 seconds and
150 km) is marked corroborated and gains EMSC as a second source; an EMSC earthquake with no USGS match becomes its own
item. A missing match is not an error by either agency: their magnitudes differ, so an event can sit just above 4.5
in one catalogue and just below it in the other."""
import json
import math
from datetime import datetime, timedelta, timezone

from .common import country_at, fetch_or_none, to_utc

URL = "https://www.seismicportal.eu/fdsnws/event/1/query?format=json&minmag=4.5&starttime={start}&limit=1000"
EVENT_PAGE = "https://www.seismicportal.eu/eventdetails.html?unid={unid}"
MATCH_SECONDS, MATCH_KM = 90, 150


def url(now: datetime) -> str:
    return URL.format(start=(now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"))


def parse(doc: dict) -> list[dict]:
    out = []
    for f in doc.get("features", []):
        p = f.get("properties") or {}
        try:
            lat, lon, mag = float(p["lat"]), float(p["lon"]), round(float(p["mag"]), 1)
        except (KeyError, TypeError, ValueError):
            continue
        region = " ".join((p.get("flynn_region") or "").split())
        cc = country_at(lat, lon)
        out.append({"id": p.get("unid") or f.get("id"), "mag": mag, "magtype": p.get("magtype"),
                    "time": to_utc(p.get("time") or ""), "updated": to_utc(p.get("lastupdate") or ""),
                    "region": region.title() if region.isupper() else region, "depth_km": p.get("depth"),
                    "authority": p.get("auth"), "lat": round(lat, 3), "lon": round(lon, 3),
                    "countries": [cc] if cc else [], "url": EVENT_PAGE.format(unid=p.get("unid"))})
    return out


def collect(old, now: datetime | None = None, fetch=fetch_or_none):
    now = now or datetime.now(timezone.utc)
    body, err = fetch(url(now), 60)
    if body is None:
        return old or [], err
    if not body.strip():
        return [], None   # FDSN services answer an empty body (HTTP 204) when nothing matches
    try:
        return parse(json.loads(body)), None
    except ValueError as e:
        return old or [], f"parse: {e}"


def _km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def match(usgs: list[dict], emsc: list[dict]) -> dict:
    """{usgs id: emsc record} for the closest EMSC event in time within the window, each EMSC event used once."""
    pairs = []
    for i, u in enumerate(usgs):
        tu = _t(u.get("time"))
        if tu is None or u.get("lat") is None:
            continue
        for j, e in enumerate(emsc):
            te = _t(e.get("time"))
            if te is None:
                continue
            dt = abs((tu - te).total_seconds())
            if dt <= MATCH_SECONDS and _km(u, e) <= MATCH_KM:
                pairs.append((dt, i, j))
    out, used_u, used_e = {}, set(), set()
    for dt, i, j in sorted(pairs):
        if i not in used_u and j not in used_e:
            used_u.add(i)
            used_e.add(j)
            out[usgs[i]["id"]] = emsc[j]
    return out
