"""A program's doctrine registers: requirements, warning problems and indicators,
assumptions, function map, and the source register.

    python doctrine/kit/tic.py registers doctrine

Each program keeps them in its own doctrine/ folder:
  requirements.json  standing questions, PIRs and EEIs mapped to data series
  indicators.json    warning problems, hypotheses and indicators
  assumptions.json   key assumptions with a test and a status
  ncf_map.json       event type -> National Critical Functions (deterministic, no AI)
  sources.json       the source register (or a pointer to the program's own register)
  method.md          the method in words
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

from . import vocab

ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$")
ASSUMPTION_STATUS = {"holds", "strained", "broken", "untested", "untestable"}
REQ_TYPES = {"standing", "pir", "eei"}
SOURCE_USE = {"ingest", "visual", "link", "excluded"}


def _load(folder: Path, name: str):
    p = folder / name
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def ids(folder: Path) -> dict:
    """Known ids, for the linter's link checks."""
    req = _load(folder, "requirements.json") or {}
    ind = _load(folder, "indicators.json") or {}
    return {
        "requirements": {r["id"] for r in req.get("requirements", [])},
        "warning_problems": {w["id"] for w in ind.get("warning_problems", [])},
        "indicators": {i["id"] for i in ind.get("indicators", [])},
    }


def check(folder: Path) -> list[str]:
    errs = []
    req = _load(folder, "requirements.json")
    ind = _load(folder, "indicators.json")
    ass = _load(folder, "assumptions.json")
    nmap = _load(folder, "ncf_map.json")
    src = _load(folder, "sources.json")
    for name, doc in (("requirements.json", req), ("indicators.json", ind), ("assumptions.json", ass),
                      ("ncf_map.json", nmap), ("sources.json", src)):
        if doc is None:
            errs.append(f"{name} missing")
    if not (folder / "method.md").exists():
        errs.append("method.md missing")

    seen = set()

    def new_id(i, where):
        if not i or not ID_RE.match(i):
            errs.append(f"{where}: id {i!r} should look like NF-PIR-1")
        if i in seen:
            errs.append(f"{where}: duplicate id {i!r}")
        seen.add(i)

    if req:
        try:
            date.fromisoformat(req.get("review_by", ""))
        except ValueError:
            errs.append("requirements.json: review_by must be a date (YYYY-MM-DD)")
        for r in req.get("requirements", []):
            new_id(r.get("id"), "requirements")
            if r.get("type") not in REQ_TYPES:
                errs.append(f"requirements {r.get('id')}: type must be one of {sorted(REQ_TYPES)}")
            if not r.get("question"):
                errs.append(f"requirements {r.get('id')}: question missing")
            if r.get("type") in ("pir", "eei") and not r.get("series"):
                errs.append(f"requirements {r.get('id')}: map it to at least one data series")

    ind_ids = set()
    if ind:
        for i in ind.get("indicators", []):
            new_id(i.get("id"), "indicators")
            ind_ids.add(i.get("id"))
            for key in ("text", "series", "rule"):
                if not i.get(key):
                    errs.append(f"indicator {i.get('id')}: {key} missing")
            g = i.get("gentry") or {}
            missing = [k for k in ("predictive", "diagnostic", "unambiguous", "collectable") if k not in g]
            if missing:
                errs.append(f"indicator {i.get('id')}: Gentry test missing {missing}")
        for w in ind.get("warning_problems", []):
            new_id(w.get("id"), "warning_problems")
            for key in ("title", "watch_condition", "issue_on_change", "deactivation", "frozen"):
                if not w.get(key):
                    errs.append(f"warning problem {w.get('id')}: {key} missing")
            hyps = w.get("hypotheses") or []
            if len(hyps) < 2:
                errs.append(f"warning problem {w.get('id')}: needs at least two hypotheses (include 'artefact or data failure')")
            for h in hyps:
                new_id(h.get("id"), f"hypotheses of {w.get('id')}")
                for lst in ("emerging", "not_emerging"):
                    for ref in h.get(lst, []):
                        if ref not in ind_ids:
                            errs.append(f"hypothesis {h.get('id')}: {lst} names unknown indicator {ref!r}")

    if ass:
        for a in ass.get("assumptions", []):
            new_id(a.get("id"), "assumptions")
            if a.get("status") not in ASSUMPTION_STATUS:
                errs.append(f"assumption {a.get('id')}: status must be one of {sorted(ASSUMPTION_STATUS)}")
            if not a.get("test"):
                errs.append(f"assumption {a.get('id')}: test missing (say 'untestable' if it is)")

    if nmap:
        for rule in nmap.get("rules", []):
            bad = [f for f in rule.get("ncf", []) if f not in vocab.ncf()]
            if bad:
                errs.append(f"ncf_map rule {rule.get('match')!r}: unknown functions {bad}")

    if src and "register" not in src:
        for s in src.get("sources", []):
            for key in ("id", "name", "licence", "use"):
                if not s.get(key):
                    errs.append(f"source {s.get('id')}: {key} missing")
            if s.get("use") and s["use"] not in SOURCE_USE:
                errs.append(f"source {s.get('id')}: use must be one of {sorted(SOURCE_USE)}")
    return errs


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    folder = Path(argv[0] if argv else "doctrine")
    errs = check(folder)
    for e in errs:
        print("  -", e)
    print(f"Doctrine registers in {folder}: {'PASS' if not errs else f'FAIL ({len(errs)} problems)'}")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
