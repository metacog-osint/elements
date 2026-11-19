"""Tradecraft linter: check feed files against contract v2 and print a pass or
fail for each of ICD 203's nine tradecraft standards.

    python doctrine/kit/tic.py lint site/data/feed.geojson [--doctrine doctrine] [--json report.json]

Exit status 1 when any error is found, so CI fails the build.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import CONTRACT, CONTRACT_REV, __version__, contract, vocab
from .registers import ids as register_ids


def read_items(path: Path) -> tuple[dict | None, list[dict]]:
    """(feed header or None, items) from .json, .geojson or .jsonl."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return None, [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return None, data
    if data.get("type") == "FeatureCollection":
        header = {k: v for k, v in data.items() if k != "features"}
        return header, data.get("features") or []
    if isinstance(data.get("items"), list):
        return {k: v for k, v in data.items() if k != "items"}, data["items"]
    return None, [data]


check_header = contract.check_header      # kept here for callers of 0.5.x


def lint_files(paths, doctrine_dir=None) -> dict:
    """Problems per standard, with up to five examples each. Revision 2.1 notices (contract.REVISION) are warnings
    only; they are counted per feed and message ("12 of 20 items: rev 2.1: subject_id absent") instead of listed per
    item. `coverage` counts the items carrying each revision 2.1 field, the migration's dashboard."""
    regs = register_ids(Path(doctrine_dir)) if doctrine_dir else None
    by_std = defaultdict(lambda: {"error": 0, "warning": 0, "examples": []})
    coverage = dict.fromkeys(contract.REVISION_FIELDS, 0)
    n_items = 0
    # What the checks could look at (kit 0.6.2, review M5): standards 4 and 7 are checked on judgments, 8 on
    # forecasts, 7 also on updates and cancellations. With none, the row says so instead of "pass".
    examined = {"judgments": 0, "forecasts": 0, "updates": 0}
    for path in map(Path, paths):
        header, items = read_items(path)
        rev = (header or {}).get("contract_rev")
        problems = [("feed", p) for p in check_header(header)] if header is not None else []
        notices = Counter()
        subjects = Counter()
        for item in items:
            n_items += 1
            props, _ = contract.split(item)
            examined["judgments"] += contract.is_judgment(props)
            examined["forecasts"] += props.get("kind") == "forecast"
            examined["updates"] += props.get("msg_type") in ("update", "cancel", "error")
            for k in contract.REVISION_FIELDS:
                coverage[k] += props.get(k) is not None
            if isinstance(props.get("subject_id"), str):
                subjects[props["subject_id"]] += 1
            for p in contract.check(item, regs, rev=rev):
                if p[0] == contract.REVISION and p[1] == "warning":
                    notices[p[2]] += 1
                else:
                    problems.append((props.get("id", "?"), p))
        shared = sum(1 for n in subjects.values() if n > 1)
        if shared:
            notices[contract.REV_NOTE + "a subject_id shared by two or more items of one feed (history keeps each "
                    "under its own id)"] += shared
        for item_id, (std, sev, msg) in problems:
            slot = by_std[std]
            slot[sev] += 1
            if len(slot["examples"]) < 5:
                slot["examples"].append(f"{path.name} {item_id}: {sev}: {msg}")
        if notices:
            slot = by_std[contract.REVISION]
            slot["warning"] += sum(notices.values())
            for msg, n in sorted(notices.items(), key=lambda kv: (-kv[1], kv[0])):
                slot["examples"].append(f"{path.name}: {n} of {len(items)} items: {msg}")
    return {"items": n_items, "standards": dict(by_std), "coverage": coverage, "examined": examined}


def not_applicable(sid: str, examined: dict | None) -> str | None:
    """Why nothing was checked under a standard, or None when something was."""
    if not examined:
        return None
    if sid == "alternatives" and not examined["judgments"]:
        return "no judgments in these files"
    if sid == "change" and not (examined["judgments"] or examined["updates"]):
        return "no judgments, updates or cancellations in these files"
    if sid == "accuracy" and not examined["forecasts"]:
        return "no forecasts in these files"
    return None


def print_report(rep: dict) -> bool:
    std = vocab.load("icd203")["tradecraft_standards"]
    ok = True
    print(f"Tradecraft linter: {rep['items']} items checked against feed contract {CONTRACT} "
          f"(revision {CONTRACT_REV}, kit {__version__})")
    print("Aligned with ICD 203's tradecraft standards (the directive binds IC elements only). A structural check:")
    print("each row says whether the fields that standard needs are present and well formed, not whether the")
    print("analysis meets it.\n")
    rows = [("general", "Contract fields, tags and vocabularies")] + [
        (s["id"], f"{s['n']}. {s['title']}: the fields it needs") for s in std]
    rows.append((contract.REVISION, f"Revision {CONTRACT_REV} fields (optional until 2.2; notices never fail a build)"))
    for sid, title in rows:
        r = rep["standards"].get(sid, {"error": 0, "warning": 0, "examples": []})
        na = not_applicable(sid, rep.get("examined"))
        if na and not (r["error"] or r["warning"]):
            print(f"  [n/a ] {title}  (not applicable: {na})")
            continue
        mark = "FAIL" if r["error"] else "pass"
        ok &= not r["error"]
        extra = f"  ({r['error']} errors, {r['warning']} warnings)" if (r["error"] or r["warning"]) else ""
        print(f"  [{mark}] {title}{extra}")
        shown = r["examples"] if sid != contract.REVISION else r["examples"][:20]
        for ex in shown:
            print(f"         {ex}")
        if len(shown) < len(r["examples"]):
            print(f"         ... {len(r['examples']) - len(shown)} more in the JSON report")
    cov = rep.get("coverage")
    if cov and rep["items"]:
        print(f"\nRevision {CONTRACT_REV} coverage: " + ", ".join(f"{k} {n}/{rep['items']}" for k, n in cov.items()))
    print("\nResult:", "PASS" if ok else "FAIL")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tic lint", description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--doctrine", help="program's doctrine/ folder, for requirement and indicator link checks")
    ap.add_argument("--json", help="also write the report as JSON to this path")
    a = ap.parse_args(argv)
    rep = lint_files(a.files, a.doctrine)
    ok = print_report(rep)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
