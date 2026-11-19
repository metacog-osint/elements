"""Load the kit's vocabulary files.

The vocab folder sits two levels above this package, both in the kit repo
(tic-doctrine/vocab) and in a vendored copy (doctrine/kit/vocab).
"""

import json
from functools import cache
from pathlib import Path

VOCAB_DIR = Path(__file__).resolve().parents[2] / "vocab"


@cache
def load(name: str) -> dict:
    with open(VOCAB_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def enum(name: str) -> set[str]:
    """Allowed values of one closed list in enums.json."""
    return set(load("enums")[name]["values"])


def zones() -> dict:
    """The suite's shared zone keys (D4, kit 0.6.1): {key: {key, name, countries, map}}, Watchfloor's catalog."""
    return {z["key"]: z for z in load("zones")["zones"]}


def retired_zones() -> dict:
    """Zone keys Watchfloor has retired: {key: {key, on, into, why, countries}}. They still resolve."""
    return {z["key"]: z for z in load("zones")["retired"]}


def zone(key: str) -> dict | None:
    """One zone by key, active or retired, or None."""
    return zones().get(key) or retired_zones().get(key)


def framework(name: str) -> dict:
    return load("frameworks")[name]


def ncf() -> dict:
    return load("infrastructure")["ncf"]


def sectors() -> dict:
    return load("infrastructure")["sectors"]


def lifelines() -> dict:
    return load("infrastructure")["lifelines"]


def ladders() -> dict:
    return load("grading")["response_stage"]["ladders"]


def admiralty() -> dict:
    return load("grading")["admiralty"]


def actor_roles() -> dict:
    """Roles an actor can play in an item: {id: {label, frame, side, meaning}}."""
    return load("actors")["roles"]["values"]


def actor_types() -> dict:
    return load("actors")["types"]["values"]


def source_owners() -> set[str]:
    return set(load("actors")["source_owner"]["values"])


def never_words() -> list[str]:
    """Words that judge a side as friend or foe; never used to characterise an actor."""
    return load("actors")["never"]


def derive_sectors(ncf_ids) -> list[str]:
    """Sectors implied by a list of National Critical Function ids, sorted."""
    table = ncf()
    out = set()
    for f in ncf_ids or []:
        out.update(table[f]["sectors"])
    return sorted(out)


def derive_lifelines(ncf_ids) -> list[str]:
    table = ncf()
    out = set()
    for f in ncf_ids or []:
        out.update(table[f]["lifelines"])
    return sorted(out)
