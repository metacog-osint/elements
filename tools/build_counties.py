"""Build catalog/us_counties.json: county GEOID (state FIPS + county FIPS, as in NWS SAME codes without the leading 0)
-> [lat, lon, name, state] from the US Census Bureau's county Gazetteer file (public domain). NWS alerts that name
counties but carry no polygon are placed at their counties' internal points. Rerun when the Census Bureau publishes a
new year.

    python tools/build_counties.py [year]
"""
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements.common import fetch  # noqa: E402

URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/{y}_Gazetteer/{y}_Gaz_counties_national.zip"
OUT = ROOT / "catalog" / "us_counties.json"


def main(argv) -> int:
    year = argv[0] if argv else "2025"
    z = zipfile.ZipFile(io.BytesIO(fetch(URL.format(y=year), 120, 16 * 1024 * 1024)))
    text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    sep = "|" if "|" in text.splitlines()[0] else "\t"   # tabs until 2024, pipes from 2025
    rows = [line.split(sep) for line in text.splitlines() if line.strip()]
    head = [h.strip() for h in rows[0]]
    col = {h: i for i, h in enumerate(head)}
    table = {}
    for r in rows[1:]:
        r = [c.strip() for c in r]
        table[r[col["GEOID"]]] = [round(float(r[col["INTPTLAT"]]), 4), round(float(r[col["INTPTLONG"]]), 4),
                                  r[col["NAME"]], r[col["USPS"]]]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"source": f"US Census Bureau, {year} Gazetteer counties file (internal points)",
                               "columns": ["lat", "lon", "name", "state"], "counties": dict(sorted(table.items()))},
                              ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(ROOT)}: {len(table)} counties")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
