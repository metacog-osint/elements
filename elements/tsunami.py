"""Tsunami messages from NOAA's two warning centres (US public domain).

Each centre's Atom feed holds its latest product; the CAP file it links to gives the alert type, the earthquake's
preliminary magnitude, origin time, depth and position. Elements keeps every message it has seen for 30 days, one
record per centre and earthquake (a later message replaces an earlier one), and publishes those from the last 7 days.

- NTWC, the National Tsunami Warning Center (Palmer, Alaska): Alaska, British Columbia, the US West Coast, the US
  Atlantic and Gulf coasts, Puerto Rico.
- PTWC, the Pacific Tsunami Warning Center (Honolulu): Hawaii, US Pacific territories, and international Pacific and
  Caribbean messages."""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from .common import country_at, fetch_or_none, to_utc

CENTRES = {"NTWC": "https://www.tsunami.gov/events/xml/PAAQAtom.xml",
           "PTWC": "https://www.tsunami.gov/events/xml/PHEBAtom.xml"}
CENTRE_NAMES = {"NTWC": "National Tsunami Warning Center", "PTWC": "Pacific Tsunami Warning Center"}
ATOM = {"a": "http://www.w3.org/2005/Atom"}
CAP = {"c": "urn:oasis:names:tc:emergency:cap:1.2"}
LEVELS = ("warning", "advisory", "watch", "threat", "information")   # highest first
KEEP_DAYS, SHOW_DAYS = 30, 7


def level_of(event: str) -> str:
    e = (event or "").lower()
    return next((lv for lv in LEVELS if lv in e), "information")


def parse_atom(body: bytes) -> list[str]:
    """The CAP links in a centre's Atom feed."""
    root = ET.fromstring(body)
    return [ln.get("href") for e in root.findall("a:entry", ATOM) for ln in e.findall("a:link", ATOM)
            if (ln.get("href") or "").endswith("CAP.xml")]


def parse_cap(body: bytes, centre: str, url: str) -> dict | None:
    root = ET.fromstring(body)
    info = root.find("c:info", CAP)
    if info is None:
        return None
    params = {p.findtext("c:valueName", namespaces=CAP): p.findtext("c:value", namespaces=CAP)
              for p in info.findall("c:parameter", CAP)}
    lat = lon = None
    m = re.match(r"\s*([-\d.]+)\s*,\s*([-\d.]+)", params.get("EventLatLon") or "")
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
    origin = to_utc(params.get("EventOriginTime") or "")
    try:
        mag = float(params.get("EventPreliminaryMagnitude") or "")
    except ValueError:
        mag = None
    depth = re.match(r"\s*([\d.]+)", params.get("EventDepth") or "")
    event = info.findtext("c:event", namespaces=CAP) or ""
    cc = country_at(lat, lon) if lat is not None else None
    return {"id": f"{centre}-{(origin or '').replace(':', '').replace('-', '')}", "centre": centre,
            "msg_type": root.findtext("c:msgType", namespaces=CAP), "sent": to_utc(root.findtext("c:sent", namespaces=CAP) or ""),
            "event": event, "level": level_of(event), "severity": info.findtext("c:severity", namespaces=CAP),
            "headline": " ".join((info.findtext("c:headline", namespaces=CAP) or "").split()),
            "location": params.get("EventLocationName") or "", "magnitude": mag,
            "magnitude_type": params.get("EventPreliminaryMagnitudeType"), "origin": origin,
            "depth_km": float(depth.group(1)) if depth else None, "lat": lat, "lon": lon,
            "countries": [cc] if cc else [], "url": url}


def collect(old, now: datetime | None = None, fetch=fetch_or_none):
    """(records, problem). A failed centre keeps its earlier records."""
    now = now or datetime.now(timezone.utc)
    keep = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = {r["id"]: r for r in old or [] if (r.get("sent") or "") >= keep}
    problems = []
    for centre, url in CENTRES.items():
        body, err = fetch(url, 40)
        if body is None:
            problems.append(f"{centre} feed: {err}")
            continue
        try:
            links = parse_atom(body)
        except ET.ParseError as e:
            problems.append(f"{centre} feed: parse: {e}")
            continue
        for link in links:
            cap, err = fetch(link, 40)
            if cap is None:
                problems.append(f"{centre} message: {err}")
                continue
            try:
                rec = parse_cap(cap, centre, link)
            except ET.ParseError as e:
                problems.append(f"{centre} message: parse: {e}")
                continue
            if rec and rec["origin"] and (rec["sent"] or "") >= keep:
                prev = records.get(rec["id"])
                if not prev or (rec["sent"] or "") >= (prev.get("sent") or ""):
                    records[rec["id"]] = rec
    out = sorted(records.values(), key=lambda r: r.get("sent") or "", reverse=True)
    return out, ("; ".join(problems) or None)
