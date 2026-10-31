"""Which countries does a point or shape fall in? (geo/countries.json, Natural Earth, public domain)

Coarse by design (rings thinned to about 5 km): use it to tag items, not to draw borders. Points at sea return no
country; maritime zones need their own layer.
"""

import json
from functools import cache
from pathlib import Path

FILE = Path(__file__).resolve().parents[2] / "geo" / "countries.json"


@cache
def _countries():
    return json.loads(FILE.read_text(encoding="utf-8"))["countries"]


def _in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def country_at(lat: float, lon: float) -> str | None:
    """ISO 3166-1 alpha-2 code at a point, or None at sea."""
    for c in _countries():
        b = c["bbox"]
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]:
            if any(_in_ring(lon, lat, r) for r in c["rings"]):
                return c["cc"]
    return None


def countries_in(points) -> list[str]:
    """Sorted country codes for any of a shape's sample points [(lat, lon), ...]."""
    return sorted({cc for cc in (country_at(la, lo) for la, lo in points) if cc})


def point(cc: str):
    """[lat, lon] label point inside the country (ISO alpha-2), or None. Natural Earth LABEL_Y/LABEL_X."""
    path = Path(__file__).resolve().parents[2] / "geo" / "points.json"
    return json.loads(path.read_text(encoding="utf-8"))["points"].get(str(cc or "").upper())


def name(cc: str) -> str | None:
    for c in _countries():
        if c["cc"] == cc:
            return c["name"]
    return None
