"""Withholding rule (modelled on ICD 191's trigger; adopted voluntarily).

If an ingested public item holds a credible, specific threat to kill, seriously
injure or kidnap an identifiable person or group, the suite does not publish or
map it. A person refers it to local law enforcement or the FBI, the decision is
logged privately with a non-identifying note, and only a monthly count is public.

    python doctrine/kit/tic.py withheld --log private/withheld.jsonl --out site/data/withheld.json

The private log is JSON lines, never tracked in a public repo:
    {"when": "2026-10-30T14:00:00Z", "program": "watchfloor", "reason": "threat_to_person",
     "note": "non-identifying description", "referred_to": "FBI tips", "reviewer": "TB"}
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REASONS = {
    "threat_to_person": "Credible, specific threat to kill, seriously injure or kidnap a person or group",
    "re_identification": "Could re-identify an individual (source terms forbid it)",
}


def record(log: Path, program: str, reason: str, note: str, referred_to: str, reviewer: str) -> dict:
    if reason not in REASONS:
        raise ValueError(f"reason must be one of {sorted(REASONS)}")
    entry = {
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "program": program, "reason": reason, "note": note,
        "referred_to": referred_to, "reviewer": reviewer,
    }
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def counts(log: Path) -> dict:
    """Public counts by month and reason. Nothing else leaves the log."""
    months = {}
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                months.setdefault(e["when"][:7], Counter())[e["reason"]] += 1
    return {
        "rule": __doc__.split("\n\n")[1].replace("\n", " "),
        "reasons": REASONS,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "months": [{"month": m, "total": sum(c.values()), "by_reason": dict(c)} for m, c in sorted(months.items())],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tic withheld")
    ap.add_argument("--log", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    data = counts(Path(a.log))
    Path(a.out).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Withheld counts: {sum(m['total'] for m in data['months'])} items over {len(data['months'])} months")
    return 0


if __name__ == "__main__":
    sys.exit(main())
