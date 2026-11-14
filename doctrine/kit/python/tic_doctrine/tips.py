"""Tips: one program reading another program's findings instead of collecting the same data again (1 Nov 2026).

Each dataset is collected once, by the program that owns it (vocab/programs.json). A program says what it wants from
the others in doctrine/interests.json; tips() matches those interests against the suite bus (COP's merged snapshot of
every live feed) or any contract-v2 feed; cite() turns a tip into a source entry for the program's own item, carrying
the upstream lineage so convergence and the two-source rule count each original source once; diff() compares two runs,
because producers do not mark changes yet.

    python doctrine/kit/tic.py tips doctrine                 # interests against the bus (plus the feeds of wanted
                                                             # programs the bus does not carry), printed by area
    python doctrine/kit/tic.py tips doctrine --feed <url>    # against one program's feed instead
    python doctrine/kit/tic.py tips doctrine --json tips.json

doctrine/interests.json:
    {"program": "watchfloor",
     "areas": {"WF-WP-Z01": ["UA"], "WF-WP-Z07": ["RU", "PL", "LT"]},     named country sets (ISO alpha-2)
     "interests": [
       {"id": "WF-INT-1", "about": "why this program wants these items",
        "programs": ["cordon"],                       required: whose items
        "areas": ["WF-WP-Z01"],                       optional: default every area; items must share a country
        "global": false,                              optional: true also takes items with no country
        "anywhere": false,                            optional: true takes every match worldwide, with or without a
                                                      country (items placed only by geometry, such as navigational
                                                      warnings, have none); areas still label the ones inside them
        "tiers": ["anomaly", "warning"],              optional filters, each a list of allowed values
        "kinds": [...], "status_class": [...],
        "response_stage_prefix": ["state_post_posture:"],
        "title_any": ["..."], "title_none": ["..."],  case-insensitive substrings
        "where": [{"path": "measures.level", "op": "gte", "value": 3}],
        "fingerprint": ["measures.level"],            optional: extra fields whose change counts as a change
        "indicator_id": "WF-IND-7"}]}                 optional: the program's own indicator this feeds

A tip is a pointer, not a copy: it keeps the producer's id, title, tier and status class. A stale producer (COP's
cop_stale on the bus, or a directly read feed built longer ago than its stale_hours in the registry) gives stale tips,
to be drawn grey, never read as quiet. An item's own age never makes it stale: standing notices can be years old.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import geo, vocab

ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$")
CC_RE = re.compile(r"^[A-Z]{2}$")
OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"}
LISTS = ("tiers", "kinds", "status_class", "response_stage_prefix", "title_any", "title_none")
FILTER_ENUMS = {"tiers": "tier", "kinds": "kind", "status_class": "status_class"}
DEFAULT_FINGERPRINT = ("tier", "kind", "status_class", "response_stage", "indicator_state", "warning_problem_id")
USER_AGENT = "tic-doctrine-tips/1 (+https://theintelligence.company)"


def registry() -> dict:
    return vocab.load("programs")


def program_entry(pid: str) -> dict:
    return next((p for p in registry()["programs"] if p["id"] == pid), {})


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def load(src: str, timeout: float = 60) -> tuple[dict, list[dict]]:
    """(header, items) from a contract-v2 FeatureCollection at a URL or a local path. Items are the features'
    properties; each gets `_program` (its own program, or COP's tag on the bus)."""
    if re.match(r"^https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            doc = json.loads(r.read().decode("utf-8"))
    else:
        doc = json.loads(Path(src).read_text(encoding="utf-8"))
    header = {k: v for k, v in doc.items() if k != "features"}
    items = []
    for f in doc.get("features") or []:
        p = dict(f.get("properties") or {})
        p["_program"] = p.get("program") or p.get("cop_program") or header.get("program")
        if f.get("geometry"):
            p["_geometry"] = f["geometry"]
        if "cop_stale" not in p:  # read directly: the feed's own build time says whether the producer is current
            p["_feed_generated"] = header.get("generated_at")
        items.append(p)
    return header, items


def gather(interests_doc: dict, bus: str | None = None, fetch=load) -> tuple[list[dict], list[dict]]:
    """Items for a program's interests: the bus, plus the feed of any wanted program the bus does not carry (or all of
    them when the bus fails). Returns (items, problems); a source that fails is listed in problems, so the consumer
    shows no data for it rather than quiet."""
    items, problems = [], []
    try:
        items = fetch(bus or registry()["bus"]["url"])[1]
    except Exception as e:  # network, HTTP or JSON: carry on with direct feeds
        problems.append({"source": "bus", "error": f"{type(e).__name__}: {e}"[:200]})
    present = {i.get("_program") for i in items}
    wanted = sorted({p for i in interests_doc.get("interests", []) for p in i.get("programs", [])})
    for pid in wanted:
        entry = program_entry(pid)
        if pid in present or entry.get("status") != "live" or not entry.get("feed"):
            continue
        try:
            items += fetch(entry["feed"])[1]
        except Exception as e:
            problems.append({"source": pid, "error": f"{type(e).__name__}: {e}"[:200]})
    return items, problems


def _get(item: dict, path: str):
    cur = item
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _cmp(v, op: str, want) -> bool:
    if v is None:
        return False
    try:
        if op == "eq":
            return v == want
        if op == "ne":
            return v != want
        if op == "gt":
            return v > want
        if op == "gte":
            return v >= want
        if op == "lt":
            return v < want
        if op == "lte":
            return v <= want
        if op == "in":
            return v in want
        if op == "contains":
            return want in v if isinstance(v, (list, str)) else False
    except TypeError:
        return False
    return False


def matches(item: dict, interest: dict) -> bool:
    """Every stated filter must pass (lists are any-of). Areas are checked separately (areas_for)."""
    if item.get("_program") not in interest.get("programs", []):
        return False
    for key, field in (("tiers", "tier"), ("kinds", "kind"), ("status_class", "status_class")):
        if interest.get(key) and item.get(field) not in interest[key]:
            return False
    if interest.get("response_stage_prefix"):
        stage = item.get("response_stage") or ""
        if not any(stage.startswith(p) for p in interest["response_stage_prefix"]):
            return False
    title = (item.get("title") or "").lower()
    if interest.get("title_any") and not any(t.lower() in title for t in interest["title_any"]):
        return False
    if any(t.lower() in title for t in interest.get("title_none", [])):
        return False
    return all(_cmp(_get(item, w["path"]), w["op"], w.get("value")) for w in interest.get("where", []))


def _area_boxes(boxes: dict | None, area: str) -> list[list[float]]:
    raw = (boxes or {}).get(area)
    if not raw or not isinstance(raw, list):
        return []
    if len(raw) == 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in raw):
        return [[float(x) for x in raw]]
    return [[float(x) for x in b] for b in raw if isinstance(b, list) and len(b) == 4]


def areas_for(item: dict, interest: dict, areas: dict[str, list[str]], boxes: dict | None = None) -> list[str] | None:
    """The interest's areas that share a country or bounding box with the item; [] for a matching item with no country
    when the interest is global; None when the item falls outside every area."""
    wanted = interest.get("areas") or list(areas)
    geom = item.get("_geometry") or item.get("geometry")
    cc = set(item.get("countries") or [])
    if not cc and geom:
        cc = set(geo.countries_for_geometry(geom))
    ibbox = geo.geometry_bbox(geom) if geom else None

    def _in_area(a: str) -> bool:
        if cc & set(areas.get(a, [])):
            return True
        if ibbox is not None:
            return any(geo.boxes_intersect(ibbox, b) for b in _area_boxes(boxes, a))
        return False

    if interest.get("anywhere"):  # worldwide: keep every match, labelled with any areas it falls in
        return [a for a in wanted if _in_area(a)]
    hit = [a for a in wanted if _in_area(a)]
    if hit:
        return hit
    if not cc and ibbox is None:
        return [] if interest.get("global") else None
    if not wanted:  # a program with no named areas takes items from anywhere
        return []
    return None


def fingerprint(item: dict, extra=()) -> str:
    """What has to change for a tip to count as changed: tier, kind, status, response stage, indicator state, the
    warning problem, plus any paths the interest names. Titles are left out (they carry counts that move daily)."""
    parts = [str(item.get(k)) for k in DEFAULT_FINGERPRINT] + [json.dumps(_get(item, p), sort_keys=True) for p in extra]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _stale(item: dict, now: datetime) -> bool:
    """Whether the producer is behind: COP's flag on the bus, or a directly read feed built longer ago than the
    program's stale_hours. An item's own age is not used: a standing notice issued in 2023 can still be in force."""
    if "cop_stale" in item:
        return bool(item["cop_stale"])
    hours = program_entry(item.get("_program") or "").get("stale_hours")
    built = _parse(item.get("_feed_generated"))
    return bool(hours and built and (now - built).total_seconds() > hours * 3600)


def tips(items: list[dict], interests_doc: dict, now: datetime | None = None) -> list[dict]:
    """Tips for one program: each item that meets an interest and falls in one of its areas. The program's own items
    are never tips to itself."""
    now = now or datetime.now(timezone.utc)
    me = interests_doc.get("program")
    areas = interests_doc.get("areas") or {}
    boxes = interests_doc.get("boxes") or {}
    out = []
    for interest in interests_doc.get("interests", []):
        for item in items:
            if item.get("_program") == me or not matches(item, interest):
                continue
            hit = areas_for(item, interest, areas, boxes)
            if hit is None:
                continue
            upstream = [{"lineage_id": s.get("lineage_id"), "independence_group": s.get("independence_group"),
                         "publisher": s.get("publisher")} for s in item.get("sources") or []]
            out.append({
                "interest_id": interest["id"], "indicator_id": interest.get("indicator_id"), "areas": hit,
                "program": item["_program"], "item_id": item.get("id"), "title": item.get("title"),
                "kind": item.get("kind"), "tier": item.get("tier"), "status_class": item.get("status_class"),
                "response_stage": item.get("response_stage"), "countries": item.get("countries") or [],
                "data_as_of": item.get("data_as_of"), "published_at": item.get("published_at"),
                "link": item.get("link"), "us_person_data": item.get("us_person_data"),
                "stale": _stale(item, now), "upstream": upstream,
                "fingerprint": fingerprint(item, interest.get("fingerprint", ())),
            })
    out.sort(key=lambda t: (t["interest_id"], t["program"], t["title"] or "", t["item_id"] or ""))
    return out


def _key(t: dict) -> tuple:
    return (t["interest_id"], t["program"], t["item_id"])


def diff(previous: list[dict], current: list[dict]) -> dict:
    """New, changed and ended tips between two runs of the same interests (producers do not mark changes yet)."""
    before = {_key(t): t for t in previous or []}
    after = {_key(t): t for t in current or []}
    return {"new": [t for k, t in after.items() if k not in before],
            "changed": [t for k, t in after.items() if k in before and before[k]["fingerprint"] != t["fingerprint"]],
            "ended": [t for k, t in before.items() if k not in after]}


def cite(tip: dict, accessed_at: datetime | None = None) -> dict:
    """A contract-v2 source entry for a consumer's item that rests on this tip. The lineage and independence group are
    the upstream source's when the producer's item has one, so a tip that traces to the same original source as
    something the consumer already holds counts once; otherwise the producer program is the lineage."""
    entry = program_entry(tip["program"])
    name = entry.get("name") or tip["program"]
    groups = sorted({u["independence_group"] for u in tip.get("upstream", []) if u.get("independence_group")})
    lineages = sorted({u["lineage_id"] for u in tip.get("upstream", []) if u.get("lineage_id")})
    src = {
        "publisher": f"{name}, The Intelligence Company",
        "licence": entry.get("terms") or f"{name} terms",
        "title": tip.get("title") or "",
        "source_type": "suite_program",
        "url": tip.get("link") or entry.get("feed") or entry.get("site") or "",
        "descriptor": f"Tip from {name}: {tip.get('tier')} {tip.get('kind')}, {tip.get('status_class')} (item {tip.get('item_id')})",
        "lineage_id": lineages[0] if len(lineages) == 1 else f"{tip['program']}:{tip.get('item_id')}",
        "independence_group": "+".join(groups) if groups else tip["program"],
        "accessed_at": _iso(accessed_at or datetime.now(timezone.utc)),
    }
    if _parse(tip.get("published_at")):
        src["published_at"] = _iso(_parse(tip["published_at"]))
    return src


def check_interests(doc: dict) -> list[str]:
    """Problems in a program's doctrine/interests.json (empty list when it is sound)."""
    errs = []
    known = {p["id"] for p in registry()["programs"]}
    me = doc.get("program")
    if not me:
        errs.append("interests.json: program missing")
    elif me not in known:
        errs.append(f"interests.json: program {me!r} is not in the suite registry (vocab/programs.json)")
    areas = doc.get("areas") or {}
    for a, cc in areas.items():
        bad = [c for c in cc if not isinstance(c, str) or not CC_RE.match(c)]
        if bad or not cc:
            errs.append(f"interests area {a}: needs ISO alpha-2 country codes (bad: {bad or 'empty'})")
    boxes = doc.get("boxes") or {}
    if not isinstance(boxes, dict):
        errs.append("interests boxes: must be an object mapping area ids to [west, south, east, north] boxes")
    else:
        for a, raw in boxes.items():
            if a not in areas:
                errs.append(f"interests box {a!r}: unknown area")
            blist = _area_boxes(boxes, a)
            if not blist or any(not (-180 <= b[0] <= b[2] <= 180 and -90 <= b[1] <= b[3] <= 90) for b in blist):
                errs.append(f"interests box {a}: needs [west, south, east, north] with west<=east and south<=north")
    seen = set()
    for i in doc.get("interests", []):
        iid = i.get("id")
        if not iid or not ID_RE.match(iid):
            errs.append(f"interest {iid!r}: id should look like WF-INT-1")
        if iid in seen:
            errs.append(f"interest {iid!r}: duplicate id")
        seen.add(iid)
        if not i.get("about"):
            errs.append(f"interest {iid}: say what it is for (about)")
        progs = i.get("programs") or []
        if not progs:
            errs.append(f"interest {iid}: name at least one program")
        for p in progs:
            if p not in known:
                errs.append(f"interest {iid}: unknown program {p!r}")
            elif p == me:
                errs.append(f"interest {iid}: a program does not tip itself")
        for a in i.get("areas") or []:
            if a not in areas:
                errs.append(f"interest {iid}: unknown area {a!r}")
        for key, enum_name in FILTER_ENUMS.items():
            bad = [v for v in i.get(key) or [] if v not in vocab.enum(enum_name)]
            if bad:
                errs.append(f"interest {iid}: {key} has unknown values {bad}")
        for key in LISTS:
            if key in i and not isinstance(i[key], list):
                errs.append(f"interest {iid}: {key} must be a list")
        for w in i.get("where") or []:
            if not w.get("path") or w.get("op") not in OPS:
                errs.append(f"interest {iid}: where needs a path and an op from {sorted(OPS)}")
    return errs


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):  # a Windows console cannot print every place name; never crash on one
        sys.stdout.reconfigure(errors="replace")
    folder = Path(argv.pop(0) if argv and not argv[0].startswith("--") else "doctrine")
    srcs, out = [], None
    while argv:
        a = argv.pop(0)
        if a in ("--bus", "--feed") and argv:
            srcs.append(argv.pop(0))
        elif a == "--json" and argv:
            out = Path(argv.pop(0))
    doc = json.loads((folder / "interests.json").read_text(encoding="utf-8"))
    errs = check_interests(doc)
    if errs:
        for e in errs:
            print("  -", e)
        print(f"interests.json in {folder}: FAIL ({len(errs)} problems)")
        return 1
    problems = []
    if srcs:
        items = []
        for src in srcs:
            items += load(src)[1]
    else:
        items, problems = gather(doc)
    for p in problems:
        print(f"  ! {p['source']}: {p['error']}")
    found = tips(items, doc)
    by_area: dict[str, list[dict]] = {}
    for t in found:
        for a in t["areas"] or ["(no country)"]:
            by_area.setdefault(a, []).append(t)
    for a in sorted(by_area):
        print(f"{a}:")
        for t in by_area[a]:
            print(f"  {t['interest_id']:<10} {t['program']:<11} {t['tier']:<8}{' STALE' if t['stale'] else ''}  {(t['title'] or '')[:90]}")
    print(f"{len(found)} tips for {doc['program']} from {len(items)} items ({', '.join(srcs) or 'the bus'})")
    if out:
        out.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
