"""Build catalog/us_reactors.json: each US power reactor unit, by the name the NRC's daily Power Reactor Status Report
gives it, -> [lat, lon, state, county FIPS, EIA plant code, plant], from FEMA's "Nuclear Plant Power Reactor Status"
feature service (a US Government work; it states no licence, and Elements credits FEMA). The NRC's own reports give
no coordinates, so this is where Elements places a reactor's status and its event notifications.

    python tools/build_reactors.py                 read the FEMA service
    python tools/build_reactors.py --from FILE DATE   a JSON list of the service's attribute rows, read some other way
                                                    on DATE (such as "25 Nov 2026")

Rerun when a unit is added, renamed or retired. tests/test_radiation.py checks every unit against its county's Census
internal point and the kit's state outlines.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements.common import fetch  # noqa: E402

SERVICE = "https://gis.fema.gov/arcgis/rest/services/Partner/Nuclear_Plant_Power_Reactor_Status/FeatureServer/0"
FIELDS = "reactor_name,latitude,longitude,state,county,fips,doe_eia_plant_code,power_plant"
OUT = ROOT / "catalog" / "us_reactors.json"
# Names an event notification may give a facility that its normalised name does not reach (elements/nrc.py drops
# words such as "nuclear", "station" and "plant", and reads "St." as "Saint", before it looks a name up).
ALIASES = {"Cook": "D.C. Cook", "Donald C. Cook": "D.C. Cook", "Crane": "Three Mile Island",
           "Crane Clean Energy Center": "Three Mile Island", "Shearon Harris": "Harris", "Joseph M. Farley": "Farley",
           "H. B. Robinson": "Robinson", "H.B. Robinson": "Robinson", "Virgil C. Summer": "Summer", "V.C. Summer": "Summer",
           "James A. FitzPatrick": "FitzPatrick", "Edwin I. Hatch": "Hatch", "Alvin W. Vogtle": "Vogtle",
           "R.E. Ginna": "Ginna", "Robert E. Ginna": "Ginna", "South Texas Project": "South Texas",
           "La Salle": "LaSalle", "La Salle County": "LaSalle", "Columbia": "Columbia Generating Station",
           "Wolf Creek Generating Station": "Wolf Creek", "Arkansas": "Arkansas Nuclear"}


def base(name: str) -> str:
    """A unit's name without its unit number: "Hope Creek 1" -> "Hope Creek"."""
    return re.sub(r"\s+\d+$", "", name.strip())


def catalog(rows: list[dict], read_on: str) -> dict:
    """The catalog from the service's attribute rows. A row with no plant name takes its sibling unit's (same EIA
    plant code, or same name without the unit number)."""
    by_eia, by_base = {}, {}
    for r in rows:
        if r.get("power_plant"):
            by_eia.setdefault(str(r.get("doe_eia_plant_code") or ""), r["power_plant"])
            by_base.setdefault(base(r["reactor_name"]), r["power_plant"])
    units = {}
    for r in rows:
        name = " ".join(str(r.get("reactor_name") or "").split())
        try:
            lat, lon = round(float(r["latitude"]), 5), round(float(r["longitude"]), 5)
        except (KeyError, TypeError, ValueError):
            continue
        if not name or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        eia = str(r.get("doe_eia_plant_code") or "") or None
        fips = str(r.get("fips") or "").zfill(5) if r.get("fips") else None
        plant = r.get("power_plant") or by_eia.get(eia or "") or by_base.get(base(name))
        units[name] = [lat, lon, (r.get("state") or "").strip() or None, fips, eia, plant]
    return {"source": f"FEMA, Nuclear Plant Power Reactor Status feature service (US Government work, no licence "
                      f"stated; credited), read {read_on}: {SERVICE}",
            "columns": ["lat", "lon", "state", "county_fips", "eia_plant", "plant"],
            "units": dict(sorted(units.items())), "aliases": dict(sorted(ALIASES.items()))}


def dumps(doc: dict) -> str:
    """One unit and one alias a line, so a changed unit reads as one changed line."""
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    units = ",\n".join(f"  {j(k)}: {j(v)}" for k, v in doc["units"].items())
    aliases = ",\n".join(f"  {j(k)}: {j(v)}" for k, v in doc["aliases"].items())
    return (f'{{"source": {j(doc["source"])},\n"columns": {j(doc["columns"])},\n"units": {{\n{units}\n}},\n'
            f'"aliases": {{\n{aliases}\n}}}}\n')


def read_service() -> list[dict]:
    q = urlencode({"where": "1=1", "outFields": FIELDS, "returnGeometry": "false", "f": "json"})
    doc = json.loads(fetch(f"{SERVICE}/query?{q}", 90))
    if "error" in doc:
        raise SystemExit(f"FEMA service error: {doc['error']}")
    return [f.get("attributes") or {} for f in doc.get("features") or []]


def main(argv) -> int:
    if argv[:1] == ["--from"]:
        rows, read_on = json.loads(Path(argv[1]).read_text(encoding="utf-8")), argv[2]
    else:
        rows, read_on = read_service(), datetime.now(timezone.utc).strftime("%d %b %Y").lstrip("0")
    doc = catalog(rows, read_on)
    OUT.write_text(dumps(doc), encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(ROOT)}: {len(doc['units'])} units")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
