"""Tradecraft linter: check feed files against contract v2 and print a pass or
fail for each of ICD 203's nine tradecraft standards.

    python doctrine/kit/tic.py lint site/data/feed.geojson [--doctrine doctrine] [--json report.json]

Exit status 1 when any error is found, so CI fails the build.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from . import CONTRACT, contract, vocab
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


def check_header(h: dict) -> list[tuple[str, str, str]]:
    out = []
    if h.get("contract") != CONTRACT:
        out.append(("general", "error", f"feed header contract must be {CONTRACT!r}"))
    for key in ("program", "generated_at", "licence", "attribution"):
        if not h.get(key):
            out.append(("general", "error", f"feed header {key} missing"))
    if not h.get("language_key"):
        out.append(("uncertainty", "warning", "feed header language_key (link to the likelihood and confidence key) missing"))
    return out


def lint_files(paths, doctrine_dir=None) -> dict:
    regs = register_ids(Path(doctrine_dir)) if doctrine_dir else None
    by_std = defaultdict(lambda: {"error": 0, "warning": 0, "examples": []})
    n_items = 0
    for path in map(Path, paths):
        header, items = read_items(path)
        problems = [("feed", p) for p in check_header(header)] if header is not None else []
        for item in items:
            n_items += 1
            props, _ = contract.split(item)
            for p in contract.check(item, regs):
                problems.append((props.get("id", "?"), p))
        for item_id, (std, sev, msg) in problems:
            slot = by_std[std]
            slot[sev] += 1
            if len(slot["examples"]) < 5:
                slot["examples"].append(f"{path.name} {item_id}: {sev}: {msg}")
    return {"items": n_items, "standards": dict(by_std)}


def print_report(rep: dict) -> bool:
    std = vocab.load("icd203")["tradecraft_standards"]
    ok = True
    print(f"Tradecraft linter: {rep['items']} items checked against feed contract {CONTRACT}")
    print("Aligned with ICD 203's tradecraft standards (the directive binds IC elements only).\n")
    rows = [("general", "Contract fields, tags and vocabularies")] + [(s["id"], f"{s['n']}. {s['title']}") for s in std]
    for sid, title in rows:
        r = rep["standards"].get(sid, {"error": 0, "warning": 0, "examples": []})
        mark = "FAIL" if r["error"] else "pass"
        ok &= not r["error"]
        extra = f"  ({r['error']} errors, {r['warning']} warnings)" if (r["error"] or r["warning"]) else ""
        print(f"  [{mark}] {title}{extra}")
        for ex in r["examples"]:
            print(f"         {ex}")
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
