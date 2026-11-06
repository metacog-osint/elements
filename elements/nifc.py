"""US wildfire incidents from the National Interagency Fire Center's WFIGS service (Wildland Fire Interagency
Geospatial Services, current incident locations). The service states no licence; Elements credits NIFC and links to
its open-data site.

Only wildfires (not prescribed burns), and only those not declared out that are either still short of 100 percent
containment or were discovered in the last 14 days: WFIGS's "current" list keeps large fires for months after they
are contained."""
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from .common import fetch_or_none

FIELDS = ("IncidentName,IncidentSize,PercentContained,FireDiscoveryDateTime,ModifiedOnDateTime_dt,POOState,POOCounty,"
          "IncidentTypeCategory,IrwinID,UniqueFireIdentifier,FireCause,IncidentComplexityLevel,FireOutDateTime")
URL = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Incident_Locations_Current/FeatureServer/0/"
       "query?where=" + quote("IncidentTypeCategory='WF'") + "&outFields=" + FIELDS + "&f=geojson")
PAGE = "https://data-nifc.opendata.arcgis.com/"
NEW_DAYS = 14


def _ms(v) -> str | None:
    try:
        return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return None


def parse(doc: dict, now: datetime) -> list[dict]:
    new_since = (now - timedelta(days=NEW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for f in doc.get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        c = g.get("coordinates") or []
        if p.get("IncidentTypeCategory") != "WF" or p.get("FireOutDateTime") or len(c) < 2:
            continue
        found = _ms(p.get("FireDiscoveryDateTime"))
        pct = p.get("PercentContained")
        if pct is not None and pct >= 100 and (found or "") < new_since:
            continue
        name = " ".join((p.get("IncidentName") or "").split())
        name = name.title() if name.isupper() else name
        state = (p.get("POOState") or "").replace("US-", "")
        out.append({"id": p.get("IrwinID") or p.get("UniqueFireIdentifier"), "name": name,
                    "acres": round(float(p.get("IncidentSize") or 0), 1), "contained": pct, "discovered": found,
                    "updated": _ms(p.get("ModifiedOnDateTime_dt")), "state": state, "county": p.get("POOCounty"),
                    "cause": p.get("FireCause"), "complexity": p.get("IncidentComplexityLevel"),
                    "lon": round(float(c[0]), 4), "lat": round(float(c[1]), 4)})
    return sorted(out, key=lambda x: -x["acres"])


def collect(old, now: datetime | None = None, fetch=fetch_or_none):
    now = now or datetime.now(timezone.utc)
    body, err = fetch(URL, 90)
    if body is None:
        return old or [], err
    try:
        doc = json.loads(body)
    except ValueError as e:
        return old or [], f"parse: {e}"
    if "error" in doc:
        return old or [], f"service error {doc['error'].get('code')}"
    return parse(doc, now), None
