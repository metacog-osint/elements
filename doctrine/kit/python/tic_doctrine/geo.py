"""Which countries does a point or shape fall in? (geo/countries.json, Natural Earth, public domain)

Coarse by design (rings thinned to about 5 km): use it to tag items, not to draw borders. Points at sea return no
country; the named sea areas are in geo/seas.json (sea_at, sea_areas_for_geometry; kit 0.6.0). Codes are ISO 3166-1 alpha-2 (Taiwan is TW, Kosovo XK), as the feed
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
    """Sorted ISO alpha-2 country codes for any vertex of a GeoJSON geometry. A shape whose vertices all lie outside
    a country it covers misses that country; revision 2.1 of the contract takes `countries` by overlap, so use
    countries_overlapping() for areas and lines."""
    return countries_in(geometry_points(geom))


# --- overlap (kit 0.6.0) -------------------------------------------------------------------------------------------
# Coordinates here are (lon, lat) as GeoJSON writes them. A shape overlaps a target when one of its points lies in
# the target, one of its edges crosses the target's outline, or the target lies wholly inside it. Shapes that cross
# the 180th meridian are not split, as elsewhere in the kit.

def _parts(geom: dict | None) -> tuple[list, list, list]:
    """(points, lines, polygons) of a GeoJSON geometry: points [(x, y)], lines [[(x, y), ...]], polygons
    [[outer, hole, ...]]."""
    pts, lines, polys = [], [], []
    if not isinstance(geom, dict):
        return pts, lines, polys
    t, c = geom.get("type"), geom.get("coordinates")
    try:
        if t == "Point":
            pts.append((float(c[0]), float(c[1])))
        elif t == "MultiPoint":
            pts += [(float(p[0]), float(p[1])) for p in c]
        elif t == "LineString":
            lines.append([(float(p[0]), float(p[1])) for p in c])
        elif t == "MultiLineString":
            lines += [[(float(p[0]), float(p[1])) for p in ln] for ln in c]
        elif t == "Polygon":
            polys.append([[(float(p[0]), float(p[1])) for p in r] for r in c])
        elif t == "MultiPolygon":
            polys += [[[(float(p[0]), float(p[1])) for p in r] for r in poly] for poly in c]
        elif t == "GeometryCollection":
            for g in geom.get("geometries") or []:
                a, b, d = _parts(g)
                pts += a
                lines += b
                polys += d
    except (TypeError, ValueError, IndexError):
        pass
    return pts, lines, polys


def _in_poly(x, y, poly) -> bool:
    """Inside a polygon's outer ring and in none of its holes."""
    return bool(poly) and _in_ring(x, y, poly[0]) and not any(_in_ring(x, y, h) for h in poly[1:])


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _cross(p1, p2, q1, q2) -> bool:
    """Whether segments p1-p2 and q1-q2 meet (touching counts)."""
    d1, d2, d3, d4 = _orient(q1, q2, p1), _orient(q1, q2, p2), _orient(p1, p2, q1), _orient(p1, p2, q2)
    if ((d1 > 0) != (d2 > 0) and d1 != 0 and d2 != 0) and ((d3 > 0) != (d4 > 0) and d3 != 0 and d4 != 0):
        return True

    def on(a, b, c):
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
    return (d1 == 0 and on(q1, q2, p1)) or (d2 == 0 and on(q1, q2, p2)) or (d3 == 0 and on(p1, p2, q1)) \
        or (d4 == 0 and on(p1, p2, q2))


def _box(seq) -> list[float]:
    xs, ys = [p[0] for p in seq], [p[1] for p in seq]
    return [min(xs), min(ys), max(xs), max(ys)]


def _edges_cross(path, rings) -> bool:
    """Whether any edge of path (a line or ring) meets any edge of rings."""
    for ring in rings:
        rb = _box(ring)
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            if not boxes_intersect(_box((a, b)), rb):
                continue
            for j in range(len(ring) - 1):
                c, d = ring[j], ring[j + 1]
                if max(c[0], d[0]) < min(a[0], b[0]) or min(c[0], d[0]) > max(a[0], b[0]) \
                        or max(c[1], d[1]) < min(a[1], b[1]) or min(c[1], d[1]) > max(a[1], b[1]):
                    continue
                if _cross(a, b, c, d):
                    return True
    return False


def _overlaps(parts, target_polys) -> bool:
    """Whether a shape (from _parts) overlaps a target given as polygons [[outer, hole, ...], ...]."""
    pts, lines, polys = parts
    vertices = pts + [p for ln in lines for p in ln] + [p for poly in polys for r in poly for p in r]
    if any(_in_poly(x, y, t) for x, y in vertices for t in target_polys):
        return True
    target_rings = [r for t in target_polys for r in t]
    if any(_edges_cross(path, target_rings) for path in lines + [r for poly in polys for r in poly]):
        return True
    # the target wholly inside the shape: then every point of its outline is, so one point says it
    return any(t and t[0] and any(_in_poly(t[0][0][0], t[0][0][1], poly) for poly in polys) for t in target_polys)


def countries_overlapping(geom: dict | None) -> list[str]:
    """Sorted ISO alpha-2 codes of the countries a GeoJSON geometry overlaps: a point in the country, an edge crossing
    its border, or the country wholly inside an area. This is the revision 2.1 meaning of `countries` for an item
    placed by its true footprint (an H3 cell over Doha names Qatar even when no corner of the cell is in Qatar). Same
    outlines as country_at(), thinned to about 5 km, so a shape that only grazes a border within that distance can
    gain or miss the neighbour."""
    parts = _parts(geom)
    if not any(parts):
        return []
    box = _box(parts[0] + [p for ln in parts[1] for p in ln] + [p for poly in parts[2] for p in poly[0]])
    found = set()
    for c in _countries():
        if c["cc"] in found or not boxes_intersect(box, c["bbox"]):
            continue
        if _overlaps(parts, [[r] for r in c["rings"]]):
            found.add(c["cc"])
    return sorted(found)


SEAS = Path(__file__).resolve().parents[2] / "geo" / "seas.json"


@cache
def _seas():
    return json.loads(SEAS.read_text(encoding="utf-8"))["seas"]


@cache
def _sea_names() -> dict:
    return {s["slug"]: s["name"] for s in _seas()}


def sea_slugs() -> set[str]:
    """Every slug in the kit's sea gazetteer (geo/seas.json): the values `sea_areas` may hold."""
    return set(_sea_names())


def sea_name(slug: str) -> str | None:
    """The gazetteer's name for a sea-area slug ("persian-gulf" -> "Persian Gulf"), or None."""
    return _sea_names().get(str(slug or ""))


def sea_at(lat: float, lon: float) -> str | None:
    """Slug of the named sea, gulf, strait or ocean at a point, or None on land or in unnamed internal waters. The
    gazetteer's areas tile the water without overlapping, so there is one at most."""
    for s in _seas():
        b = s["bbox"]
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and any(_in_poly(lon, lat, poly) for poly in s["polygons"]):
            return s["slug"]
    return None


def sea_areas_for_geometry(geom: dict | None) -> list[str]:
    """Sorted slugs of the sea areas a GeoJSON geometry overlaps, for an item's `sea_areas` ([] on land). Areas are
    Natural Earth's 1:10m marine areas (geo/seas.json, built by tools/build_seas.py), rounded to about 1 km: a point
    within that distance of a coast or a border between two areas can fall either side. Natural Earth has no separate Strait of Hormuz (it lies in
    the Persian Gulf and the Gulf of Oman) and no canals."""
    parts = _parts(geom)
    if not any(parts):
        return []
    box = _box(parts[0] + [p for ln in parts[1] for p in ln] + [p for poly in parts[2] for p in poly[0]])
    return sorted(s["slug"] for s in _seas() if boxes_intersect(box, s["bbox"]) and _overlaps(parts, s["polygons"]))


SUBDIVISIONS = Path(__file__).resolve().parents[2] / "geo" / "subdivisions.json"


@cache
def _subdivisions():
    return json.loads(SUBDIVISIONS.read_text(encoding="utf-8"))["subdivisions"]


def subdivision_at(lat: float, lon: float) -> str | None:
    """ISO 3166-2 code of the state at a point ("US-HI"), or None at sea, outside the covered countries (the United
    States for now; territories such as Puerto Rico have their own ISO country code). Outlines are Natural Earth
    1:10m (geo/subdivisions.json): within about 1 km of a state line or coast a point can get the neighbour or None
    (checked 15 Nov 2026: Fargo ND, West Fargo ND and Moorhead MN right; at Grand Forks the line sits about 1 km east
    of the Red River)."""
    for sd in _subdivisions():
        b = sd["bbox"]
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and any(_in_ring(lon, lat, r) for r in sd["rings"]):
            return sd["code"]
    return None


def _outer_rings(geom: dict | None) -> list:
    if not geom:
        return []
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon":
        return [c[0]]
    if t == "MultiPolygon":
        return [p[0] for p in c]
    if t == "GeometryCollection":
        return [r for g in geom.get("geometries") or [] for r in _outer_rings(g)]
    return []


def subdivisions_for_geometry(geom: dict | None) -> list[str]:
    """Sorted ISO 3166-2 codes of the states a GeoJSON geometry touches: any of its vertices falls in the state, or
    (for an area) any point of the state's outline falls inside it, so an area around a small state (the DC area
    TFR around the District of Columbia) names that state too."""
    found = {s for s in (subdivision_at(la, lo) for la, lo in geometry_points(geom)) if s}
    rings = _outer_rings(geom)
    box = geometry_bbox(geom) if rings else None
    if box:
        for sd in _subdivisions():
            if sd["code"] in found or not boxes_intersect(box, sd["bbox"]):
                continue
            # about 32 points of the state's outline: enough to see a state the area encloses (a state the area only
            # crosses already holds one of the area's vertices)
            pts = [q for ring in sd["rings"] for q in ring]
            if any(_in_ring(x, y, r) for x, y in pts[::max(1, len(pts) // 32)] for r in rings):
                found.add(sd["code"])
    return sorted(found)


def point(cc: str):
    """[lat, lon] label point inside the country (ISO alpha-2), or None. Natural Earth LABEL_Y/LABEL_X."""
    return _points().get(str(cc or "").upper())


def name(cc: str) -> str | None:
    """Full country name for an ISO alpha-2 code ("SS" -> "South Sudan"), or None."""
    return _names().get(str(cc or "").upper())
