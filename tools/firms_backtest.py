"""Back-test of the FIRMS country anomaly rule on the seasonal record (catalog/firms_climatology.json.gz), 2022-2025,
and a replay on the live record (data/firms_daily.json).

    python tools/firms_backtest.py

The archive's NOAA-20 counts are multiplied by feed.FIRE_CLIM_SATS to stand for the live two-satellite count. Each
rule is judged on the country-days with at least feed.FIRE_MIN detections, the days that would have had a feed item.
  R0    elements-feed-1.2: feed.fire_baseline (median of the past 28 days on file), at least FIRE_MULT times it and
        at least FIRE_FLOOR detections
  hold  R0 while the country crossed R0 on no more than 5% of those 28 days (a flag-rate hold, for comparison)
  PR    elements-feed-1.3: feed.fire_rule, R0 and above the seasonal threshold of feed.fire_seasonal
The tested countries are those R0 flagged on more than 5% of their days in the live record of 13-26 Nov 2026, and 8
controls. The named episodes and their date windows are set from public reports of each fire (see the method note);
the peak is the highest day in the window.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed  # noqa: E402

TESTED = ["CI", "KH", "UG", "EC", "TG", "CO", "GR", "BJ", "GH", "TH", "VN", "HN", "IT", "DE", "NI", "ZA", "GB", "GA",
          "LA", "PE", "PG", "BF", "NG", "BO", "MX", "ID", "PT", "ES", "CL"]
EPISODES = [  # (label, country, first day, last day)
    ("Greece, Evros, Aug-Sep 2023", "GR", "2023-08-19", "2023-09-05"),
    ("Italy, Sicily, Jul 2023", "IT", "2023-07-24", "2023-07-26"),
    ("Thailand, haze, Mar 2023", "TH", "2023-03-01", "2023-03-31"),
    ("Laos, haze, Mar 2023", "LA", "2023-03-01", "2023-03-31"),
    ("Cambodia, haze, Mar 2023", "KH", "2023-03-01", "2023-03-31"),
    ("Colombia, Jan 2024", "CO", "2024-01-20", "2024-01-31"),
    ("Chile, Valparaiso, Feb 2024", "CL", "2024-02-02", "2024-02-05"),
    ("Honduras, Apr-May 2024", "HN", "2024-04-15", "2024-05-31"),
    ("Bolivia, Aug-Sep 2024", "BO", "2024-08-01", "2024-09-30"),
    ("Ecuador, Sep 2024", "EC", "2024-09-01", "2024-09-30"),
    ("Peru, Sep 2024", "PE", "2024-09-01", "2024-09-30"),
    ("Portugal, Aveiro and Viseu, Sep 2024", "PT", "2024-09-15", "2024-09-20"),
    ("Spain, Ourense and Leon, Aug 2025", "ES", "2025-08-08", "2025-08-25"),
    ("Portugal, Arganil, Aug 2025", "PT", "2025-08-13", "2025-08-24"),
]
PEERS = [
    ("Chile, Nuble and Biobio, Feb 2023", "CL", "2023-02-01", "2023-02-15"),
    ("Greece, Rhodes, Jul 2023", "GR", "2023-07-17", "2023-07-28"),
    ("Spain, Sierra de la Culebra, Jun 2022", "ES", "2022-06-15", "2022-06-20"),
    ("Spain, Losacio, Jul 2022", "ES", "2022-07-15", "2022-07-22"),
    ("Portugal, Serra da Estrela, Aug 2022", "PT", "2022-08-06", "2022-08-16"),
    ("Indonesia, Sep-Oct 2023", "ID", "2023-09-01", "2023-10-31"),
    ("Greece, Attica, Aug 2024", "GR", "2024-08-11", "2024-08-13"),
]
ONSET = {"GH": (10, 11, 12), "BJ": (10, 11, 12), "TG": (10, 11, 12), "CI": (10, 11, 12), "NG": (10, 11, 12),
         "BF": (10, 11, 12), "UG": (11, 12), "KH": (11, 12, 1), "TH": (11, 12, 1), "LA": (11, 12, 1), "VN": (11, 12, 1)}
RULES = ("R0", "hold", "PR")
FROM, TO = "2022-01-01", "2025-12-31"
CAP = 0.05


def run(clim: dict, ccs) -> dict:
    """{cc: {day: (n, {rule: flagged})}} for the evaluated country-days."""
    first = date.fromisoformat(clim["first"])
    days = [(first + timedelta(i)).isoformat() for i in range(len(next(iter(clim["countries"].values()))))]
    valid = [i for i, d in enumerate(days) if d not in set(clim["gaps"])]
    out = {}
    for cc in ccs:
        s = clim["countries"][cc]
        n = {days[i]: s[i] * feed.FIRE_CLIM_SATS for i in valid}
        order = [days[i] for i in valid]
        crossed, res = {}, {}
        for k, d in enumerate(order):
            if k < feed.FIRE_BASE_DAYS:
                continue
            prior = {x: {cc: n[x]} for x in order[k - feed.FIRE_BASE_DAYS:k]}
            base = feed.fire_baseline(prior, cc, d)
            c = n[d] >= feed.FIRE_FLOOR and n[d] >= feed.FIRE_MULT * base["median"]
            crossed[d] = c
            if not (FROM <= d <= TO) or n[d] < feed.FIRE_MIN:
                continue
            past = order[k - feed.FIRE_BASE_DAYS:k]
            rate = sum(crossed.get(x, False) for x in past) / len(past)
            pr, _ = feed.fire_rule(n[d], base, feed.fire_seasonal(clim, cc, d))
            res[d] = (n[d], {"R0": c, "hold": c and rate <= CAP, "PR": pr})
        out[cc] = res
    return out


def episode(res, cc, a, b, rule):
    w = sorted((d, v) for d, v in res[cc].items() if a <= d <= b)
    if not w:
        return 0, None, None, False
    peak = max(w, key=lambda x: x[1][0])
    f = [d for d, v in w if v[1][rule]]
    return len(f), (f[0] if f else None), peak, peak[1][1][rule]


def main() -> int:
    clim = feed.fire_climatology()
    print(f"climatology: {len(clim['countries'])} countries, {clim['first']} to {clim['last']}, gap days {clim['gaps']}")
    res = run(clim, TESTED)

    print("\n## Tested countries, 2022-2025")
    print("| Rule | Flags | Share of country-days | Countries over 5% of own days | Named episodes kept (of 14) "
          "| Peak day flagged | Peers kept (of 7) |")
    print("|---|---|---|---|---|---|---|")
    tot = sum(len(r) for r in res.values())
    for rule in RULES:
        flags = sum(v[1][rule] for r in res.values() for v in r.values())
        over = sum(1 for r in res.values() if r and sum(v[1][rule] for v in r.values()) / len(r) > CAP)
        kept = sum(1 for _, cc, a, b in EPISODES if episode(res, cc, a, b, rule)[0])
        pk = sum(1 for _, cc, a, b in EPISODES if episode(res, cc, a, b, rule)[3])
        peers = sum(1 for _, cc, a, b in PEERS if episode(res, cc, a, b, rule)[0])
        print(f"| {rule} | {flags:,} | {flags / tot:.1%} | {over} | {kept} | {pk} | {peers} |")
    print(f"({tot:,} country-days evaluated)")

    print("\n## Per country: flagged share of its own evaluated days, 2022-2025 (highest single year in brackets)")
    print("| Country | Days | R0 | hold | PR | PR over 5% |")
    print("|---|---|---|---|---|---|")
    for cc in sorted(res, key=lambda c: -sum(v[1]["PR"] for v in res[c].values()) / max(1, len(res[c]))):
        r = res[cc]
        cells = []
        for rule in RULES:
            share = sum(v[1][rule] for v in r.values()) / len(r)
            yrs = {}
            for d, v in r.items():
                e = yrs.setdefault(d[:4], [0, 0])
                e[0] += v[1][rule]
                e[1] += 1
            hi = max(yrs.items(), key=lambda x: x[1][0] / x[1][1])
            cells.append(f"{share:.1%} ({hi[0]} {hi[1][0] / hi[1][1]:.1%})")
        prs = sum(v[1]["PR"] for v in r.values()) / len(r)
        print(f"| {cc} | {len(r)} | " + " | ".join(cells) + f" | {'yes' if prs > CAP else ''} |")

    print("\n## Named episodes: flagged days (first flagged day; * = peak day flagged)")
    print("| Episode | Peak | " + " | ".join(RULES) + " |")
    print("|---|---|" + "---|" * len(RULES))
    for label, cc, a, b in EPISODES + PEERS:
        _, _, peak, _ = episode(res, cc, a, b, "R0")
        cells = []
        for rule in RULES:
            k, f, _, pk = episode(res, cc, a, b, rule)
            cells.append(f"{k}" + (f" ({f[5:]}{'*' if pk else ''})" if f else ""))
        print(f"| {label} | {peak[0][5:]}, {peak[1][0]:,} | " + " | ".join(cells) + " |")

    print("\n## Dry-season onset months: flagged share of those country-days")
    print("| Country | Months | " + " | ".join(RULES) + " |")
    print("|---|---|" + "---|" * len(RULES))
    for cc, months in ONSET.items():
        r = [v for d, v in res[cc].items() if int(d[5:7]) in months]
        print(f"| {cc} | {','.join(map(str, months))} | "
              + " | ".join(f"{sum(v[1][rule] for v in r) / len(r):.1%}" for rule in RULES) + " |")

    allres = run(clim, sorted(clim["countries"]))
    tot = sum(len(r) for r in allres.values())
    print(f"\n## Every country in the climatology, 2022-2025 ({sum(1 for r in allres.values() if r)} countries with "
          f"an evaluated day, {tot:,} country-days)")
    print("| Rule | Flags | Share | Countries over 5% of own days |")
    print("|---|---|---|---|")
    for rule in RULES:
        flags = sum(v[1][rule] for r in allres.values() for v in r.values())
        over = sorted(cc for cc, r in allres.items() if r and sum(v[1][rule] for v in r.values()) / len(r) > CAP)
        print(f"| {rule} | {flags:,} | {flags / tot:.1%} | {len(over)}" + (f": {' '.join(over)}" if rule == "PR" else "")
              + " |")

    live = json.loads((ROOT / "data" / "firms_daily.json").read_text(encoding="utf-8"))["days"]
    ks = sorted(live)
    ev = {"R0": [], "PR": []}
    nd = 0
    for d in ks[:-1] if ks and ks[-1] >= date.today().isoformat() else ks:
        for cc, n in live[d].items():
            base = feed.fire_baseline(live, cc, d)
            if base is None or n < feed.FIRE_MIN:
                continue
            nd += 1
            if n >= feed.FIRE_FLOOR and n >= feed.FIRE_MULT * base["median"]:
                ev["R0"].append((d, cc, n))
            seas = feed.fire_seasonal(clim, cc, d)
            if feed.fire_rule(n, base, seas)[0]:
                ev["PR"].append((d, cc, n, seas["threshold"] if seas else None))
    print(f"\n## Live record (data/firms_daily.json, {ks[0]} to {ks[-1]}): {nd:,} country-days evaluated")
    for rule in ("R0", "PR"):
        print(f"{rule}: {len(ev[rule])} flags in {len({x[1] for x in ev[rule]})} countries")
    for d, cc, n, t in ev["PR"]:
        print(f"  PR {d} {cc} {n:,} (seasonal threshold {t if t is None else f'{t:,.0f}'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
