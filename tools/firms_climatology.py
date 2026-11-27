"""Per-country daily FIRMS detection counts from NASA's yearly country files: the record behind the seasonal fire
baseline (feed.fire_seasonal).

    python tools/firms_climatology.py fetch <work folder> <year> [<year> ...]
    python tools/firms_climatology.py build <work folder>

fetch reads every country entry of FIRMS's yearly archive zip for VIIRS on NOAA-20, standard processing
(https://firms.modaps.eosdis.nasa.gov/data/country/zips/viirs-jpss1_<year>_all_countries.zip; no key or login) by HTTP
Range requests, inflates each entry in memory and keeps only counts. A detection counts when its confidence is nominal
or high, as in the live record. Each half-degree cell's detections on a UTC day go to the country at that day's centre
of detections in the cell, the way elements/firms.py counts the live record, and with the same country outlines (the
doctrine kit's geo/countries.json). Nothing raw is written: <work folder>/counts_<year>.json holds per-country daily
counts, and FIRMS's own per-country totals beside them for comparison.

build merges the years into catalog/firms_climatology.json.gz. A day with no detection anywhere in the world is a gap
in the archive, not a day without fires: it is written as null and left out of every baseline. NOAA-20's record starts
on 1 Apr 2018. The yearly files come out months after the year ends, so the file is rebuilt once a year, when the
last year's file appears.
"""
import gzip
import json
import struct
import sys
import time
import urllib.request
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://firms.modaps.eosdis.nasa.gov/data/country/zips/viirs-jpss1_{y}_all_countries.zip"
OUT = ROOT / "catalog" / "firms_climatology.json.gz"
FIRST_DAY = "2018-04-01"  # NOAA-20 VIIRS in FIRMS (FIRMS FAQ)
CELL = 0.5
UA = {"User-Agent": "elements-firms-climatology/1.0"}
CHUNK = 8 * 1024 * 1024


def _get(url, a=None, b=None, method="GET"):
    h = dict(UA)
    if a is not None:
        h["Range"] = f"bytes={a}-{b}"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h, method=method), timeout=300) as r:
                return r.read() if method == "GET" else r.headers
        except Exception as e:  # noqa: BLE001 - retried, then raised
            print(f"retry {a}-{b}: {type(e).__name__}", file=sys.stderr, flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"range {a}-{b} failed")


def central_dir(url):
    """{entry name: (method, compressed size, offset)} from the zip's central directory (zip64 aware)."""
    n = int(_get(url, method="HEAD")["Content-Length"])
    tail = _get(url, max(0, n - 131072), n - 1)
    i = tail.rfind(b"PK\x05\x06")
    count, = struct.unpack("<H", tail[i + 10:i + 12])
    cd_size, cd_off = struct.unpack("<II", tail[i + 12:i + 20])
    if cd_off == 0xFFFFFFFF or count == 0xFFFF:
        j = tail.rfind(b"PK\x06\x06")
        count, cd_size, cd_off = struct.unpack("<QQQ", tail[j + 32:j + 56])
    cd = _get(url, cd_off, cd_off + cd_size - 1)
    out, p = {}, 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        method, = struct.unpack("<H", cd[p + 10:p + 12])
        csize, usize = struct.unpack("<II", cd[p + 20:p + 28])
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off, = struct.unpack("<I", cd[p + 42:p + 46])
        name = cd[p + 46:p + 46 + nl].decode("utf-8", "replace")
        extra, q = cd[p + 46 + nl:p + 46 + nl + el], 0
        while q < len(extra):
            hid, hl = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:
                vals = list(struct.unpack("<" + "Q" * (hl // 8), extra[q + 4:q + 4 + (hl // 8) * 8]))
                if usize == 0xFFFFFFFF:
                    usize = vals.pop(0)
                if csize == 0xFFFFFFFF:
                    csize = vals.pop(0)
                if off == 0xFFFFFFFF:
                    off = vals.pop(0)
            q += 4 + hl
        out[name] = (method, csize, off)
        p += 46 + nl + el + cl
    return out


def entry_lines(url, meta):
    """The entry's CSV lines, inflated chunk by chunk."""
    method, csize, off = meta
    h = _get(url, off, off + 29)
    nl, el = struct.unpack("<HH", h[26:30])
    start = off + 30 + nl + el
    z = zlib.decompressobj(-15) if method == 8 else None
    rest, pos, end = b"", start, start + csize
    while pos < end:
        b = _get(url, pos, min(end, pos + CHUNK) - 1)
        pos += len(b)
        rest += z.decompress(b) if z else b
        *lines, rest = rest.split(b"\n")
        yield from lines
    if z:
        rest += z.flush()
    if rest:
        yield from rest.split(b"\n")


class Outlines:
    """geo.country_at, with each ring's bounding box checked first: the same answer, much faster. A half-degree cell
    that no outline edge enters lies wholly in one country or wholly at sea, so its answer is found once."""

    def __init__(self):
        doc = json.loads((ROOT / "doctrine" / "kit" / "geo" / "countries.json").read_text(encoding="utf-8"))
        self.cs = []
        for c in doc["countries"]:
            rings = [(min(x for x, _ in r), min(y for _, y in r), max(x for x, _ in r), max(y for _, y in r), r)
                     for r in c["rings"]]
            self.cs.append((c["cc"], c["bbox"], rings))
        self.edged, self.whole = set(), {}
        for c in doc["countries"]:
            for r in c["rings"]:
                for (xa, ya), (xb, yb) in zip(r, r[1:] + r[:1]):
                    for ix in range(int((min(xa, xb) + 180) // CELL), int((max(xa, xb) + 180) // CELL) + 1):
                        for iy in range(int((min(ya, yb) + 90) // CELL), int((max(ya, yb) + 90) // CELL) + 1):
                            self.edged.add((ix, iy))

    @staticmethod
    def _in_ring(x, y, ring):  # as tic_doctrine.geo._in_ring
        inside, j = False, len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        return inside

    def in_cell(self, ix, iy, lat, lon):
        """The country at (lat, lon), a point in cell (ix, iy)."""
        if (ix, iy) in self.edged:
            return self.country_at(lat, lon)
        if (ix, iy) not in self.whole:
            self.whole[ix, iy] = self.country_at(iy * CELL - 90 + CELL / 2, ix * CELL - 180 + CELL / 2)
        return self.whole[ix, iy]

    def country_at(self, lat, lon):
        for cc, b, rings in self.cs:
            if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]:
                for x0, y0, x1, y1, r in rings:
                    if x0 <= lon <= x1 and y0 <= lat <= y1 and self._in_ring(lon, lat, r):
                        return cc
        return None


def fetch_year(work: Path, y: int, geo: Outlines):
    url = URL.format(y=y)
    cd = central_dir(url)
    names = sorted(k for k in cd if k.lower().endswith(".csv"))
    cells, firms_tot, t0, done = {}, {}, time.time(), 0
    for k in names:
        country = k.rsplit("/", 1)[-1][:-4].split(f"_{y}_", 1)[-1]
        tot = firms_tot.setdefault(country, {})
        it = entry_lines(url, cd[k])
        head = next(it).decode().strip().split(",")
        ila, ilo, idt, ico = (head.index(c) for c in ("latitude", "longitude", "acq_date", "confidence"))
        for line in it:
            f = line.decode("utf-8", "replace").split(",")
            if len(f) <= max(ila, ilo, idt, ico) or f[ico].strip().lower()[:1] not in ("n", "h"):
                continue
            lat, lon, day = float(f[ila]), float(f[ilo]), f[idt]
            tot[day] = tot.get(day, 0) + 1
            key = (int((lon + 180) // CELL), int((lat + 90) // CELL), day)
            c = cells.get(key)
            if c is None:
                cells[key] = [1, lon, lat]
            else:
                c[0] += 1
                c[1] += lon
                c[2] += lat
        done += cd[k][1]
    counts, unplaced = {}, 0
    for (ix, iy, day), (n, sx, sy) in cells.items():
        cc = geo.in_cell(ix, iy, sy / n, sx / n)
        if cc is None:
            unplaced += n
            continue
        e = counts.setdefault(cc, {})
        e[day] = e.get(day, 0) + n
    out = {"year": y, "source": url, "entries": len(names), "compressed_bytes": done, "cell_days": len(cells),
           "unplaced": unplaced, "elements": counts, "firms": firms_tot}
    (work / f"counts_{y}.json").write_text(json.dumps(out, sort_keys=True), encoding="utf-8")
    print(f"{y}: {len(names)} entries, {done / 1e6:.0f} MB compressed, {len(cells):,} cell-days, "
          f"{sum(sum(v.values()) for v in counts.values()):,} placed, {unplaced:,} at sea, {time.time() - t0:.0f} s",
          flush=True)


def build(work: Path):
    years = sorted(int(p.stem.split("_")[1]) for p in work.glob("counts_*.json"))
    per = {}
    for y in years:
        doc = json.loads((work / f"counts_{y}.json").read_text(encoding="utf-8"))
        for cc, days in doc["elements"].items():
            per.setdefault(cc, {}).update(days)
    first, last = date.fromisoformat(FIRST_DAY), date(years[-1], 12, 31)
    days = [(first + timedelta(i)).isoformat() for i in range((last - first).days + 1)]
    world = {d: sum(v.get(d, 0) for v in per.values()) for d in days}
    gaps = [d for d in days if not world[d]]
    doc = {"source": "NASA FIRMS, VIIRS NOAA-20 (JPSS-1) active fire product, standard processing: yearly country "
                     "files, https://firms.modaps.eosdis.nasa.gov/data/country/",
           "credit": "NASA FIRMS",
           "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "counts": "nominal- and high-confidence detections per UTC day, each half-degree cell counted to the "
                     "country at that day's centre of its detections (kit geo/countries.json); NOAA-20 only",
           "first": FIRST_DAY, "last": days[-1], "gaps": gaps,
           "countries": {cc: [None if d in gaps else v.get(d, 0) for d in days] for cc, v in sorted(per.items())}}
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(doc, f, separators=(",", ":"))
    print(f"{OUT.name}: {len(per)} countries, {days[0]} to {days[-1]}, {len(gaps)} gap days {gaps}, "
          f"{OUT.stat().st_size / 1e6:.2f} MB")


def main(argv):
    if len(argv) >= 3 and argv[0] == "fetch":
        work, geo = Path(argv[1]), Outlines()
        work.mkdir(parents=True, exist_ok=True)
        for y in argv[2:]:
            if not (work / f"counts_{y}.json").exists():
                fetch_year(work, int(y), geo)
        return 0
    if len(argv) == 2 and argv[0] == "build":
        build(Path(argv[1]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
