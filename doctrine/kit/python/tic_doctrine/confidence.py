"""Rule-based confidence (low, moderate, high) with its basis and what would raise it.

The factors follow the NIC's 2021 estimative-language section, grouped under the
UK's three factors. The thresholds are the suite's own design (vocab/confidence.json).
Confidence is never written in the same sentence as a likelihood term.
"""

from dataclasses import dataclass, field

from . import vocab

LEVELS = ["low", "moderate", "high"]
RANK = {k: i for i, k in enumerate(LEVELS)}


@dataclass
class Evidence:
    """Inputs the program can compute. Leave a field None when it does not apply."""

    independent_lines: int = 1          # distinct independence groups that agree
    contradicted: bool = False          # any independent line points the other way
    data_age_s: float | None = None     # now - data_as_of
    expected_cadence_s: float | None = None
    coverage_fraction: float | None = None
    grades: list[str] = field(default_factory=list)   # Admiralty, e.g. ["B2", "C3"]
    alternatives_rejected: int | None = None          # None: not a judgment (an observation)
    method_scored: bool = False         # Verdict holds a scored record for this method version
    assumption_status: str | None = None  # worst linked: holds, strained, broken, untested, untestable
    ease_of_faking: str | None = None   # low, medium, high
    horizon_days: float | None = None   # forecasts only


def _defaults(overrides):
    d = dict(vocab.load("confidence")["defaults"])
    d.update(overrides or {})
    return d


def assess(ev: Evidence, **overrides) -> dict:
    """Return {level, blocked, caps, basis, raise_by, label, rubric}.

    Start from the level the independent lines support, then apply every cap.
    """
    d = _defaults(overrides)
    basis, caps, raise_by = {}, [], []

    # Consistency sets the starting level.
    n = max(int(ev.independent_lines or 0), 0)
    basis["independent_lines"] = n
    basis["contradicted"] = bool(ev.contradicted)
    if n >= d["high_min_lines"] and not ev.contradicted:
        level = "high"
    elif n >= d["moderate_min_lines"]:
        level = "moderate"
        if ev.contradicted:
            raise_by.append("resolve the contradicting line of evidence")
        else:
            raise_by.append(f"a further independent line of evidence (have {n}, High needs {d['high_min_lines']})")
    else:
        level = "low"
        raise_by.append(f"a second independent line of evidence (have {n})")

    def cap(to, factor, why, fix=None):
        caps.append({"factor": factor, "to": to, "why": why})
        if fix:
            raise_by.append(fix)

    # Timeliness.
    if ev.data_age_s is not None and ev.expected_cadence_s:
        ratio = ev.data_age_s / ev.expected_cadence_s
        basis["age_vs_cadence"] = round(ratio, 2)
        if ratio > d["stale_factor"]:
            cap("low", "timeliness", f"data are {ratio:.1f}x the expected cadence old", "fresher data")

    # Extent.
    if ev.coverage_fraction is not None:
        basis["coverage_fraction"] = round(ev.coverage_fraction, 3)
        if ev.coverage_fraction < d["coverage_floor"]:
            cap("low", "extent", f"coverage {ev.coverage_fraction:.0%} is below the {d['coverage_floor']:.0%} floor",
                "fuller coverage of the area or period")

    # Source quality.
    if ev.grades:
        basis["grades"] = sorted(set(ev.grades))
        weak = [g for g in ev.grades if g[:1].upper() in ("E", "F") or g[1:2] in ("5", "6")]
        if weak:
            cap("moderate", "source_quality", f"weak or ungraded source ({', '.join(sorted(set(weak)))})",
                "a better-graded source")

    # Argumentation (judgments only).
    if ev.alternatives_rejected is not None:
        basis["alternatives_rejected"] = ev.alternatives_rejected
        if ev.alternatives_rejected < d["high_min_alternatives"]:
            cap("moderate", "argumentation", "no alternative examined and rejected",
                "examine and reject at least one alternative explanation")

    # Expertise: a scored track record.
    basis["method_scored"] = bool(ev.method_scored)
    if not ev.method_scored:
        cap("moderate", "expertise", "method version has no scored track record yet",
            "a scored Verdict record for this method version")

    # Assumptions.
    blocked = False
    if ev.assumption_status:
        basis["assumptions"] = ev.assumption_status
        if ev.assumption_status == "strained":
            cap("moderate", "assumptions", "a linked assumption is strained", "re-test the strained assumption")
        elif ev.assumption_status == "broken":
            blocked = True
            cap("low", "assumptions", "a linked assumption is broken: do not publish")

    # Deception potential.
    if ev.ease_of_faking:
        basis["ease_of_faking"] = ev.ease_of_faking
        if ev.ease_of_faking == "high":
            cap("moderate", "deception", "evidence is easy to fake", "evidence that is hard to fake")

    # Horizon.
    if ev.horizon_days is not None:
        basis["horizon_days"] = ev.horizon_days
        if ev.horizon_days > d["max_high_horizon_days"]:
            cap("moderate", "horizon", f"forecast horizon over {d['max_high_horizon_days']} days")

    for c in caps:
        if RANK[c["to"]] < RANK[level]:
            level = c["to"]

    # Only list fixes that would actually raise the level.
    if level == "high":
        raise_by = []
    return {
        "level": level,
        "blocked": blocked,
        "caps": caps,
        "basis": basis,
        "raise_by": list(dict.fromkeys(raise_by)),
        "label": vocab.load("confidence")["label"],
        "rubric": "tic-confidence-" + vocab.load("confidence")["version"],
    }


def fields(ev: Evidence, **overrides) -> dict:
    """Contract fields: confidence and confidence_basis."""
    r = assess(ev, **overrides)
    return {
        "confidence": r["level"],
        "confidence_basis": {
            "rubric": r["rubric"],
            "factors": r["basis"],
            "caps": [c["factor"] for c in r["caps"]],
            "raise_by": r["raise_by"],
        },
    }
