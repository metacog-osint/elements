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


def _walk_coords(coords, out: list[tuple[float, float]]):
    if not isinstance(coords, (list, tuple)) or not coords:
        return
    if isinstance(coords[0], (int, float)) and len(coords) >= 2 and not isinstance(coords[0], bool):
        out.append((float(coords[1]), float(coords[0])))
        return
    for item in coords:
        _walk_coords(item, out)


def geometry_points(geom: dict | None) -> list[tuple[float, float]]:
    """[(lat, lon), ...] extracted from any GeoJSON geometry object."""
    if not isinstance(geom, dict):
        return []
    out: list[tuple[float, float]] = []
    if geom.get("type") == "GeometryCollection":
        for g in geom.get("geometries") or []:
            out.extend(geometry_points(g))
    else:
        _walk_coords(geom.get("coordinates"), out)
    return out


def geometry_bbox(geom: dict | None) -> list[float] | None:
    """[west, south, east, north] bounding box for a GeoJSON geometry, or None."""
    pts = geometry_points(geom)
    if not pts:
        return None
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    return [min(lons), min(lats), max(lons), max(lats)]


def boxes_intersect(a: list[float], b: list[float]) -> bool:
    """Whether two [west, south, east, north] bounding boxes overlap."""
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def countries_for_geometry(geom: dict | None) -> list[str]:
    """Sorted ISO alpha-2 country codes for any vertex of a GeoJSON geometry."""
    return countries_in(geometry_points(geom))


def point(cc: str):
    """[lat, lon] label point inside the country (ISO alpha-2), or None. Natural Earth LABEL_Y/LABEL_X."""
    return _points().get(str(cc or "").upper())


def name(cc: str) -> str | None:
    """Full country name for an ISO alpha-2 code ("SS" -> "South Sudan"), or None."""
    return _names().get(str(cc or "").upper())
