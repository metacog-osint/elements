"""Build catalog/meteoalarm_areas.json: MeteoAlarm region code (EMMA_ID) -> [lat, lon, name, country], one point
inside each region, from MeteoAlarm's geocodes file (gitlab.com/meteoalarm-pm-group/documents, about 33 MB; no
licence stated, credited). MeteoAlarm warnings that name regions but carry no polygon are placed at these points. Only
the points are kept, not the outlines. Rerun when MeteoAlarm publishes a new geocodes file.

    python tools/build_meteoalarm_areas.py [file name]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements.common import fetch  # noqa: E402
from elements.meteoalarm import rep_point  # noqa: E402

BASE = "https://gitlab.com/meteoalarm-pm-group/documents/-/raw/master/"
NAME = "MeteoAlarm_Geocodes_2026_07_31.json"
OUT = ROOT / "catalog" / "meteoalarm_areas.json"


def points(doc: dict) -> dict:
    table = {}
    for f in doc.get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        if not p.get("code") or g.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        pt = rep_point([[[[float(x), float(y)] for x, y, *_ in ring] for ring in poly] for poly in polys])
        if pt:
            table[p["code"]] = [pt[1], pt[0], " ".join((p.get("name") or "").split()), p.get("country")]
    return table


def main(argv) -> int:
    name = argv[0] if argv else NAME
    table = points(json.loads(fetch(BASE + name, 180, 64 * 1024 * 1024)))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"source": f"MeteoAlarm geocodes file {name} (one point inside each region)",
                               "columns": ["lat", "lon", "name", "country"], "areas": dict(sorted(table.items()))},
                              ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(ROOT)}: {len(table)} regions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
