"""Back-test of the FIRMS country anomaly rule against a calendar-window (seasonal) baseline.

    python tools/firms_seasonal_backtest.py fetch  <counts.json> <years, e.g. 2018,2019> [ISO2 codes, comma-separated]
    python tools/firms_seasonal_backtest.py replay <counts.json> <results.csv>

fetch reads FIRMS's open yearly country files (VIIRS NOAA-20, standard processing; no key or login) out of the
per-year zip at firms.modaps.eosdis.nasa.gov/data/country/zips/, one zip entry per country by HTTP Range requests,
inflated in memory. It keeps only per-day counts per country: [nominal and high confidence, of which type 0
(presumed vegetation fire), low confidence]. Nothing raw is written. Countries are as FIRMS assigns them, not
Elements' half-degree cell centres.

replay doubles the NOAA-20 counts to stand in for the live two-satellite record (NOAA-20 and NOAA-21; the ratio
measured on the public 7-day files for 21-26 Nov 2026 was 1.98) and evaluates each country-day of 2022-2025 with at
least 10 detections under these rules (floor 50 detections in every rule):
  R0   elements-feed-1.2: at least 3 times the median of the past 28 days
  A    R0, held routine while the country crossed R0 on more than 5% of its past 28 days
  B    at least 3 times the median of the same +-15-day calendar window in earlier years (at least 3 years)
  P    above the 95th percentile of that same window in earlier years
  PR   P and R0 together
  PRA  PR, held routine while the country crossed PR on more than 5% of its past 28 days
The CSV gives, per country and calendar month, the country-days evaluated and the flags under each rule.
Days on which no country in the set has a row (NOAA-20 data gaps) are left out.
"""
import csv
import json
import os
import statistics
import struct
import sys
import time
import urllib.request
import zlib
from datetime import date, timedelta

ZIP = "https://firms.modaps.eosdis.nasa.gov/data/country/zips/viirs-jpss1_{y}_all_countries.zip"
UA = {"User-Agent": "elements-backtest"}
NAMES = dict(CI="Cote_d_Ivoire", EC="Ecuador", TG="Togo", CO="Colombia", KH="Cambodia", UG="Uganda", GR="Greece",
             BJ="Benin", TH="Thailand", GH="Ghana", VN="Vietnam", DE="Germany", NI="Nicaragua", ZA="South_Africa",
             IT="Italy", HN="Honduras", GB="United_Kingdom", GA="Gabon", PE="Peru", LA="Lao_PDR", PG="Papua_New_Guinea",
             BF="Burkina_Faso", NG="Nigeria", BO="Bolivia", MX="Mexico", ID="Indonesia", PT="Portugal", ES="Spain",
             CL="Chile")
K, MIN, FLOOR, MULT, BASE, WIN, CAP = 2.0, 10, 50, 3, 28, 15, 0.05
RULES = ["R0", "A", "B", "P", "PR", "PRA"]


def _get(url, a, b):
    err = None
    for t in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={**UA, "Range": f"bytes={a}-{b}"}),
                                          timeout=120)
        except OSError as e:
            err = e
            time.sleep(5 * (t + 1))
    raise err


def _directory(url):
    head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=UA), timeout=60)
    size = int(head.headers["Content-Length"])
    end = _get(url, size - 65536, size - 1).read()
    i = end.rfind(b"PK\x05\x06")
    cds, cdo = struct.unpack("<II", end[i + 12:i + 20])
    cd = _get(url, cdo, cdo + cds - 1).read()
    out, p = {}, 0
    while cd[p:p + 4] == b"PK\x01\x02":
        meth, = struct.unpack("<H", cd[p + 10:p + 12])
        cs, = struct.unpack("<I", cd[p + 20:p + 24])
        n, e, c = struct.unpack("<HHH", cd[p + 28:p + 34])
        lho, = struct.unpack("<I", cd[p + 42:p + 46])
        out[cd[p + 46:p + 46 + n].decode("utf-8", "replace")] = (meth, cs, lho)
        p += 46 + n + e + c
    return out


def _lines(url, meth, cs, lho):
    h = _get(url, lho, lho + 29).read()
    n, e = struct.unpack("<HH", h[26:30])
    start = lho + 30 + n + e
    r = _get(url, start, start + cs - 1)
    z = zlib.decompressobj(-15) if meth == 8 else None
    buf = b""
    while True:
        chunk = r.read(1 << 20)
        if not chunk:
            break
        buf += z.decompress(chunk) if z else chunk
        *lines, buf = buf.split(b"\n")
        yield from lines
    if z:
        buf += z.flush()
    if buf:
        yield from buf.split(b"\n")


def fetch(path, years, ccs):
    agg = json.load(open(path)) if os.path.exists(path) else {}
    for y in years:
        url = ZIP.format(y=y)
        d = _directory(url)
        for cc in ccs:
            key = f"viirs-jpss1/{y}/viirs-jpss1_{y}_{NAMES[cc]}.csv"
            if f"{cc}:{y}" in agg.get("_done", []) or key not in d:
                continue
            cols, days = None, agg.setdefault(cc, {})
            for ln in _lines(url, *d[key]):
                s = ln.decode("utf-8", "replace").strip().split(",")
                if cols is None:
                    cols = {k: i for i, k in enumerate(s)}
                    continue
                if len(s) < len(cols):
                    continue
                v = days.setdefault(s[cols["acq_date"]], [0, 0, 0])
                if s[cols["confidence"]] in ("n", "h"):
                    v[0] += 1
                    v[1] += s[cols["type"]] == "0" if "type" in cols else 1
                else:
                    v[2] += 1
            agg.setdefault("_done", []).append(f"{cc}:{y}")
            print(y, cc, d[key][1], "bytes", flush=True)
            json.dump(agg, open(path, "w"))


def replay(path, out_csv):
    agg = json.load(open(path))
    ccs = [c for c in agg if not c.startswith("_")]
    d0, d1 = date(2018, 4, 1), date(2025, 12, 31)
    alldays = [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]
    gap = {d for d in alldays if all(d.isoformat() not in agg[c] for c in ccs)}
    table = {}
    for c in ccs:
        s = {d: K * (agg[c].get(d.isoformat()) or [0])[0] for d in alldays if d not in gap}

        def base28(d):
            v = [s[d - timedelta(i)] for i in range(1, BASE + 1) if (d - timedelta(i)) in s]
            return statistics.median(v) if len(v) >= 14 else None

        def clim(d):
            vals, used = [], 0
            for y in range(2018, d.year):
                try:
                    m = d.replace(year=y)
                except ValueError:
                    m = d.replace(year=y, day=28)
                w = [m + timedelta(i) for i in range(-WIN, WIN + 1)]
                if all(d0 <= x <= d1 for x in w):
                    vv = [s[x] for x in w if x in s]
                    if len(vv) >= 20:
                        vals += vv
                        used += 1
            if used < 3:
                return None
            vals.sort()
            return statistics.median(vals), vals[int(0.95 * (len(vals) - 1))]

        cr = {k: {} for k in ("R0", "B", "P", "PR")}
        info = {}
        for d in s:
            if d < date(2021, 11, 1):
                continue
            n, m, cl = s[d], base28(d), clim(d)
            info[d] = (n, m, cl)
            cr["R0"][d] = m is not None and n >= FLOOR and n >= MULT * m
            cr["B"][d] = cl is not None and n >= FLOOR and n >= MULT * cl[0]
            cr["P"][d] = cl is not None and n >= FLOOR and n > cl[1]
            cr["PR"][d] = cr["P"][d] and cr["R0"][d]

        def held(kind, d):
            prior = [d - timedelta(i) for i in range(1, BASE + 1) if (d - timedelta(i)) in cr[kind]]
            return len(prior) >= 14 and sum(cr[kind][x] for x in prior) / len(prior) > CAP

        for d, (n, m, cl) in info.items():
            if d.year < 2022 or n < MIN or m is None or cl is None:
                continue
            f = {k: cr[k][d] for k in ("R0", "B", "P", "PR")}
            f["A"] = f["R0"] and not held("R0", d)
            f["PRA"] = f["PR"] and not held("PR", d)
            row = table.setdefault((c, d.month), [0] + [0] * len(RULES))
            row[0] += 1
            for i, r in enumerate(RULES):
                row[1 + i] += int(f[r])
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["country", "month", "country_days"] + [f"flags_{r}" for r in RULES])
        for (c, m), row in sorted(table.items()):
            w.writerow([c, m] + row)
    print("left out (no rows in any country):", sorted(x.isoformat() for x in gap))
    tot = [sum(r[i] for r in table.values()) for i in range(len(RULES) + 1)]
    print("country-days", tot[0], {r: f"{tot[1 + i]} ({100 * tot[1 + i] / tot[0]:.2f}%)" for i, r in enumerate(RULES)})


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "fetch":
        fetch(a[1], [int(y) for y in a[2].split(",")], a[3].split(",") if len(a) > 3 else list(NAMES))
    elif len(a) == 3 and a[0] == "replay":
        replay(a[1], a[2])
    else:
        print(__doc__)
        sys.exit(2)
