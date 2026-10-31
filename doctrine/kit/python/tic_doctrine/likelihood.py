"""Probability to ICD 203 likelihood term, and back.

Store the number. Show the term with its band ("Likely (55-80%)"). Put the UK
yardstick term in a tooltip. Never put a confidence level in the same sentence.
"""

from . import vocab


def terms() -> list[dict]:
    return vocab.load("likelihood")["terms"]


def term_for(p: float) -> dict:
    """The ICD 203 term for probability p (0 to 1).

    Overlapping band edges are resolved symmetrically about 0.5:
    below 0.05 almost no chance; [0.05, 0.20) very unlikely; [0.20, 0.45)
    unlikely; [0.45, 0.55] roughly even; (0.55, 0.80] likely; (0.80, 0.95]
    very likely; above 0.95 almost certain.
    """
    if not isinstance(p, (int, float)) or isinstance(p, bool) or not 0.0 <= p <= 1.0:
        raise ValueError(f"probability must be a number from 0 to 1, got {p!r}")
    t = terms()
    if p < 0.05:
        return t[0]
    if p < 0.20:
        return t[1]
    if p < 0.45:
        return t[2]
    if p <= 0.55:
        return t[3]
    if p <= 0.80:
        return t[4]
    if p <= 0.95:
        return t[5]
    return t[6]


def by_id(term_id: str) -> dict:
    for t in terms():
        if t["id"] == term_id:
            return t
    raise KeyError(term_id)


def label(p: float) -> str:
    """'Likely (55-80%)'."""
    t = term_for(p)
    return f"{t['term']} ({t['band_label']})"


def tooltip(p: float) -> str:
    """UK yardstick equivalent for a tooltip."""
    t = term_for(p)
    return f"UK yardstick: {t['uk']['term']} ({t['uk']['band_label']})"


def fields(p: float) -> dict:
    """The contract fields for a probability: probability and likelihood_term."""
    return {"probability": round(float(p), 4), "likelihood_term": term_for(p)["id"]}


def normalise(probs: dict) -> dict:
    """Make probabilities over mutually exclusive, exhaustive hypotheses sum to 1.

    Coherent probabilities cut analysts' error by 35% in Mandel, Karvetski and
    Dhami (2018); publish only normalised sets.
    """
    total = sum(probs.values())
    if total <= 0:
        raise ValueError("probabilities must sum to more than 0")
    return {k: v / total for k, v in probs.items()}


def change(prior_p, new_p) -> str:
    """change_from_prior value for a likelihood change, by ICD 203 step."""
    if prior_p is None:
        return "new"
    a, b = term_for(prior_p)["step"], term_for(new_p)["step"]
    if b > a:
        return "raised"
    if b < a:
        return "lowered"
    return "unchanged"
