"""Which countries does a point or shape fall in? (geo/countries.json, Natural Earth, public domain)

Coarse by design (rings thinned to about 5 km): use it to tag items, not to draw borders. Points at sea return no
country; maritime zones need their own layer. Codes are ISO 3166-1 alpha-2 (Taiwan is TW, Kosovo XK), as the feed
contract requires, and names are full names ("South Sudan", not "S. Sudan").
"""

import json
from functools import cache
from pathlib import Path

FILE = Path(__file__).resolve().parents[2] / "geo" / "countries.json"
POINTS = Path(__file__).resolve().parents[2] / "geo" / "points.json"


@cache
def _countries():
    return json.loads(FILE.read_text(encoding="utf-8"))["countries"]


@cache
def _names():
    out = {}
    for c in _countries():
        out.setdefault(c["cc"], c["name"])
    return out


@cache
def _points():
    return json.loads(POINTS.read_text(encoding="utf-8"))["points"]


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
    return _points().get(str(cc or "").upper())


def name(cc: str) -> str | None:
    """Full country name for an ISO alpha-2 code ("SS" -> "South Sudan"), or None."""
    return _names().get(str(cc or "").upper())
