"""Feed contract v2: check one item and report problems against ICD 203's nine
tradecraft standards.

An item is a GeoJSON Feature (contract fields in "properties") or a plain object
holding the same fields with an optional "geometry". Problems are tuples of
(standard_id, severity, message) where severity is "error" or "warning".
"""

import math
import re
from datetime import datetime, timedelta, timezone

from . import CONTRACT, CONTRACT_REV, likelihood, vocab

UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?Z$")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
SUBDIVISION_RE = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")  # ISO 3166-2, e.g. US-HI, GB-SCT
SUBJECT_RE = re.compile(r"^[^\s:]+(:[^\s:]+){2,}$")       # program:kind:key
DATED_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
KIT_RE = re.compile(r"^\d+\.\d+\.\d+$")
JUDGED_KINDS = {"assessment", "forecast"}

# Standard 0 holds contract-level problems that no ICD 203 standard covers.
GENERAL = "general"
# Revision 2.1 notices (kit 0.6.0): a new optional field is absent, or an item reads against the 2.1 meaning of a
# field. Always warnings, so they never fail a build; the linter counts them per feed instead of listing each item.
REVISION = "revision"
REV_NOTE = "rev 2.1: "

# Revision 2.1 item fields, in the order the contract document gives them. The linter reports how many items carry
# each, which is the migration's coverage count.
REVISION_FIELDS = ("last_change", "last_change_at", "event_start", "event_end", "event_time_precision", "subject_id",
                   "signal", "sea_areas", "place_basis", "corroboration")
HEALTH_KEYS = ("state", "checked_at", "last_ok", "last_error", "failures", "data_as_of", "detail")
# The reader's key to likelihood and confidence terms (kit 0.6.2, kit review M1): the kit repo is public, so every
# feed links this one page rather than a vendored copy in a program's repo.
LANGUAGE_KEY_URL = "https://github.com/metacog-osint/tic-doctrine/blob/main/docs/language-key.md"
HOLD_HOURS = 72          # D5: an event or notice is an anomaly within 72 hours of its change, unless the program says
FLAG_RATE_CAP = 0.05     # D5: a series flagged on more than 5% of its baseline readings is not an anomaly rule


def parse_utc(v) -> datetime | None:
    """A contract time (ISO 8601 UTC ending in Z) as an aware datetime, or None if it is not one."""
    if not isinstance(v, str) or not UTC_RE.match(v):
        return None
    try:
        return datetime.fromisoformat(v[:-1] + "+00:00")
    except ValueError:
        return None


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _floor(dt: datetime, precision: str | None) -> datetime:
    if precision == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    if precision == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if precision == "month":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt


def _period_end(dt: datetime, precision: str | None) -> datetime:
    """The end of the hour, day or month that dt starts (dt itself with no precision)."""
    dt = _floor(dt, precision)
    if precision == "hour":
        return dt + timedelta(hours=1)
    if precision == "day":
        return dt + timedelta(days=1)
    if precision == "month":
        return dt.replace(year=dt.year + dt.month // 12, month=dt.month % 12 + 1)
    return dt


def event_interval(item: dict) -> tuple[datetime | None, datetime | None] | None:
    """(start, end) of what the item describes in the world, by the revision 2.1 rules, so no reader writes the
    arithmetic twice. None when the item gives no event time.

    - With event_end, the event runs from event_start to event_end.
    - With no event_end, it runs from event_start to data_as_of (ongoing as of the last look); or, when event_start
      is later than data_as_of (something scheduled), it is that moment alone (start == end).
    - With event_time_precision (hour, day, month), event_start covers its whole period from its first instant and
      event_end its whole period to its last, so a day-precision event on 15 Nov runs 15 Nov 00:00 to 16 Nov 00:00.
    - With event_end and no event_start, start is None: the end is known, the start is not."""
    p, _ = split(item)
    prec = p.get("event_time_precision") if p.get("event_time_precision") in ("hour", "day", "month") else None
    es, ee = parse_utc(p.get("event_start")), parse_utc(p.get("event_end"))
    if es is None and ee is None:
        return None
    start = _floor(es, prec) if es else None
    if ee is not None:
        return start, _period_end(ee, prec)
    asof = parse_utc(p.get("data_as_of"))
    if asof is None or es > asof:
        return start, (_period_end(es, prec) if prec else start)
    return start, asof


def check_signal(sig, err) -> None:
    """signal: the one number the item's tier rests on, with its baseline (revision 2.1, F4)."""
    if not isinstance(sig, dict):
        err(GENERAL, "signal must be an object {name, value, ...}")
        return
    if not isinstance(sig.get("name"), str) or not sig["name"].strip():
        err(GENERAL, "signal.name missing (what is measured)")
    if not _finite(sig.get("value")):
        err(GENERAL, "signal.value must be a finite number")
    for key in ("expected",):
        if sig.get(key) is not None and not _finite(sig[key]):
            err(GENERAL, f"signal.{key} must be a finite number")
    if sig.get("unit") is not None and not isinstance(sig["unit"], str):
        err(GENERAL, "signal.unit must be a string")
    if sig.get("tail") is not None and sig["tail"] not in vocab.enum("signal_tail"):
        err(GENERAL, f"signal.tail={sig['tail']!r} not in {sorted(vocab.enum('signal_tail'))}")
    n = sig.get("baseline_n")
    if n is not None and not (isinstance(n, int) and not isinstance(n, bool) and n >= 0):
        err(GENERAL, "signal.baseline_n must be a whole number of readings, 0 or more")
        n = None
    ex = sig.get("exceedance")
    if ex is not None:
        if not _finite(ex) or not 0 <= ex <= 1:
            err(GENERAL, "signal.exceedance must be a share from 0 to 1")
        elif n and ex < 1 / (n + 1) - 1e-9:
            err(GENERAL, f"signal.exceedance {ex} is finer than a baseline of {n} readings can show "
                         f"(smallest is 1 in {n + 1})")


def check_corroboration(c, published, err) -> None:
    """D11 (kit 0.6.2): an event item's corroboration member, "reported, then corroborated". Errors only."""
    if not isinstance(c, dict):
        err(GENERAL, "corroboration must be an object")
        return
    state, basis = c.get("state"), c.get("basis")
    if state not in vocab.enum("corroboration_state"):
        err(GENERAL, f"corroboration.state={state!r} not in {sorted(vocab.enum('corroboration_state'))}")
    if basis is not None and basis not in vocab.enum("corroboration_basis"):
        err(GENERAL, f"corroboration.basis={basis!r} not in {sorted(vocab.enum('corroboration_basis'))}")
    n = c.get("origins")
    if not (isinstance(n, int) and not isinstance(n, bool) and n >= 1):
        err(GENERAL, "corroboration.origins must be a whole number of independent origins, at least 1")
        n = None
    if not (isinstance(c.get("rule"), str) and c["rule"].strip()):
        err(GENERAL, "corroboration.rule missing: print the rule's id and text (e.g. 'corroborate-1: two independent "
                     "origins, or one official source within its remit')")
    pc = c.get("party_claim", False)
    if not isinstance(pc, bool):
        err(GENERAL, "corroboration.party_claim must be true or false")
    first = parse_utc(c.get("first_reported_at"))
    if first is None:
        err(GENERAL, "corroboration.first_reported_at must be a UTC time (when the first origin appeared)")
    at_raw = c.get("corroborated_at")
    at = parse_utc(at_raw)
    if state == "reported":
        if basis is not None or at_raw is not None:
            err(GENERAL, "a reported item has basis and corroborated_at null: the rule is not met yet")
    elif state == "corroborated":
        if basis is None:
            err(GENERAL, "a corroborated item names its basis: origins or official")
        if at is None:
            err(GENERAL, "a corroborated item needs corroborated_at, a UTC time (when the rule was met)")
        if basis == "origins" and n is not None and n < 2:
            err(GENERAL, "corroborated on origins needs origins of 2 or more")
        if basis == "official" and not (isinstance(c.get("official"), str) and c["official"]):
            err(GENERAL, "corroborated on official needs official: the issuer's source id")
        if pc is True and not (n is not None and n >= 2):
            err(GENERAL, "a party's claim is corroborated only by an origin outside the party: origins of 2 or more")
    if basis != "official" and c.get("official") is not None:
        err(GENERAL, "corroboration.official is the issuer's id only when basis is official; otherwise null")
    if first and at and at < first:
        err(GENERAL, "corroboration.corroborated_at is before first_reported_at")
    if at and published and at > published:
        err(GENERAL, "corroboration.corroborated_at is after published_at")


def check_health(health, strict: bool = False) -> list[tuple[str, str, str]]:
    """The feed header's health member (revision 2.1, F6): {lane: {state, checked_at, last_ok, last_error, failures,
    data_as_of, detail}}, one entry per source lane, written on every run. Other keys are allowed. Problems are
    warnings, or errors when the feed states contract_rev 2.1 (strict)."""
    out = []
    sev = "error" if strict else "warning"
    std = GENERAL if strict else REVISION
    pre = "" if strict else REV_NOTE

    def bad(msg):
        out.append((std, sev, pre + msg))

    if not isinstance(health, dict):
        bad("feed header health must be an object keyed by lane id")
        return out
    states = vocab.enum("health_state")
    for lane_id, e in health.items():
        tag = f"health[{lane_id!r}]"
        if not isinstance(e, dict):
            bad(f"{tag} must be an object")
            continue
        if e.get("state") not in states:
            bad(f"{tag}.state={e.get('state')!r} not in {sorted(states)}")
        if parse_utc(e.get("checked_at")) is None:
            bad(f"{tag}.checked_at must be ISO 8601 UTC ending in Z")
        if "last_ok" not in e:
            bad(f"{tag}.last_ok missing (null if never read well)")
        elif e["last_ok"] is not None and parse_utc(e["last_ok"]) is None:
            bad(f"{tag}.last_ok must be ISO 8601 UTC ending in Z, or null")
        if e.get("last_error") is not None and not isinstance(e["last_error"], str):
            bad(f"{tag}.last_error must be a string or null")
        f = e.get("failures")
        if f is not None and not (isinstance(f, int) and not isinstance(f, bool) and f >= 0):
            bad(f"{tag}.failures must be a whole number, 0 or more")
        if e.get("data_as_of") is not None and parse_utc(e["data_as_of"]) is None:
            bad(f"{tag}.data_as_of must be ISO 8601 UTC ending in Z")
        if e.get("detail") is not None and not isinstance(e["detail"], str):
            bad(f"{tag}.detail must be a string")
    return out


def check_header(h: dict) -> list[tuple[str, str, str]]:
    """Problems with a feed header (the FeatureCollection's members other than features)."""
    out = []
    if h.get("contract") != CONTRACT:
        out.append((GENERAL, "error", f"feed header contract must be {CONTRACT!r}"))
    for key in ("program", "generated_at", "licence", "attribution"):
        if not h.get(key):
            out.append((GENERAL, "error", f"feed header {key} missing"))
    if not h.get("language_key"):
        out.append(("uncertainty", "warning", "feed header language_key (link to the likelihood and confidence key) missing"))
    elif h["language_key"] != LANGUAGE_KEY_URL:
        out.append(("uncertainty", "warning", f"feed header language_key should be the kit's public key "
                                              f"{LANGUAGE_KEY_URL} (a vendored copy goes stale)"))
    rev = h.get("contract_rev")
    if rev is None:
        out.append((REVISION, "warning", REV_NOTE + "feed header contract_rev absent"))
    elif rev not in vocab.enum("contract_rev"):
        out.append((GENERAL, "error", f"feed header contract_rev={rev!r} not in {sorted(vocab.enum('contract_rev'))}"))
    kit = h.get("kit")
    if kit is None:
        out.append((REVISION, "warning", REV_NOTE + "feed header kit (the vendored kit version) absent"))
    elif not (isinstance(kit, str) and KIT_RE.match(kit)):
        out.append((GENERAL, "error", f"feed header kit={kit!r} must be a kit version such as '0.6.0'"))
    if h.get("health") is None:
        out.append((REVISION, "warning", REV_NOTE + "feed header health absent"))
    else:
        out += check_health(h["health"], strict=rev == CONTRACT_REV)
    return out


def split(item: dict) -> tuple[dict, object]:
    """(properties, geometry) for a Feature or a flat item."""
    if item.get("type") == "Feature":
        return item.get("properties") or {}, item.get("geometry")
    return item, item.get("geometry")


def is_judgment(p: dict) -> bool:
    return p.get("tier") == "warning" or p.get("kind") in JUDGED_KINDS


# Actor types that are organizations, for the us_person_data cross-check.
ORG_TYPES = {"government", "armed_forces", "security_service", "armed_group", "criminal_group", "political_group",
             "company", "intergovernmental", "ngo", "media"}


def _never_re():
    words = sorted(vocab.never_words(), key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


def _check_actors(actors: list, p: dict, judged: bool, err, warn) -> None:
    """actors[]: who plays what part, as the cited sources describe it. Roles, never friend or foe."""
    roles, types = vocab.actor_roles(), vocab.actor_types()
    never = _never_re()
    source_ids = {s.get("id") for s in (p.get("sources") or []) if isinstance(s, dict) and s.get("id")}
    names_orgs = names_people = False
    for i, a in enumerate(actors):
        tag = f"actors[{i}]"
        if not isinstance(a, dict):
            err(GENERAL, f"{tag} must be an object")
            continue
        if not a.get("name"):
            err(GENERAL, f"{tag}.name missing")
        role = a.get("role")
        if role not in roles:
            err(GENERAL, f"{tag}.role={role!r} not in {sorted(roles)}")
            role = None
        kind = a.get("actor_type")
        if kind is not None and kind not in types:
            err(GENERAL, f"{tag}.actor_type={kind!r} not in {sorted(types)}")
        if a.get("status_class") not in vocab.enum("status_class"):
            err("distinguish", f"{tag}.status_class must be assessed, reported or claimed")

        side = a.get("side")
        if role and roles[role]["side"] == "required" and not side:
            err(GENERAL, f"{tag}: a {role} needs side (the party, named as the sources name it)")
        if role and roles[role]["side"] == "none" and side:
            warn(GENERAL, f"{tag}: a third party has no side; say what it does in function")
        if isinstance(side, str) and never.search(side):
            err(GENERAL, f"{tag}.side={side!r} judges friend or foe; name the party as the sources do")

        ids = a.get("source_ids")
        if ids is not None and (not isinstance(ids, list) or not all(isinstance(x, str) for x in ids)):
            err("sources", f"{tag}.source_ids must be a list of sources[].id values")
            ids = None
        if role == "responsible" and not ids:
            err("sources", f"{tag}: holding an actor responsible needs source_ids (the evidence for it)")
        for sid in ids or []:
            if sid not in source_ids:
                err("sources", f"{tag}.source_ids has {sid!r}, which is not a sources[].id in this item")
        if role == "responsible" and a.get("status_class") == "assessed" and not judged:
            err("distinguish", f"{tag}: an attribution the suite makes is a judgment; use kind=assessment "
                               "with likelihood, confidence and alternatives")

        if role == "civilians" and kind == "individual":
            err(GENERAL, f"{tag}: civilians are a population or group, never named individuals")
        if a.get("country") is not None and not (isinstance(a["country"], str) and COUNTRY_RE.match(a["country"])):
            err(GENERAL, f"{tag}.country must be an ISO 3166-1 alpha-2 code")
        for j, d in enumerate(a.get("designations") or []):
            if not isinstance(d, dict) or not d.get("by") or not d.get("label"):
                err(GENERAL, f"{tag}.designations[{j}] needs by and label, quoted as published")
        names_people |= kind == "individual"
        names_orgs |= kind in ORG_TYPES

    upd = p.get("us_person_data")
    if names_people and upd != "individuals":
        err(GENERAL, "actors name an individual: us_person_data must be 'individuals'")
    elif names_orgs and upd == "none":
        err(GENERAL, "actors name organizations: us_person_data must be 'organizations' or 'individuals'")


def _check_zone_subject(sid: str, warn) -> None:
    """D4 (kit 0.6.1): a subject of kind zone (program:zone:key, the key optionally followed by -suffix or more
    parts, as Vis's stations are) names a zone in the shared list, vocab/zones.json. Warnings only: a zone Watchfloor
    adds reaches the kit after it reaches the feeds."""
    parts = sid.split(":")
    if parts[1] != "zone":
        return
    key = parts[2].split("-")[0]
    if key in vocab.zones():
        return
    old = vocab.retired_zones().get(key)
    if old:
        warn(GENERAL, f"subject_id zone {key!r} was retired on {old['on']} into {', '.join(old['into'])}")
    else:
        warn(GENERAL, f"subject_id zone {key!r} is not in the shared zone list (vocab/zones.json, Watchfloor's)")


def _check_revision(p: dict, geom, strict: bool, err, warn) -> None:
    """Revision 2.1 (kit 0.6.0): the new optional fields' shape when present (errors), their absence (warnings), the
    tightened meanings of data_as_of and tier anomaly (warnings, or errors under strict for data_as_of)."""
    def note(msg):
        warn(REVISION, REV_NOTE + msg)

    published = parse_utc(p.get("published_at"))

    # data_as_of, tightened: the newest observation or source statement, never later than publication.
    asof = parse_utc(p.get("data_as_of"))
    if asof and published and asof > published:
        msg = "data_as_of is later than published_at: it is the newest observation, never after publication"
        (err("sources", msg) if strict else note(msg))

    # F1. Changed or standing.
    lc, lca = p.get("last_change"), p.get("last_change_at")
    if lc is not None and lc not in vocab.enum("last_change"):
        err(GENERAL, f"last_change={lc!r} not in {sorted(vocab.enum('last_change'))}")
    if lca is not None and parse_utc(lca) is None:
        err(GENERAL, f"last_change_at={lca!r} is not ISO 8601 UTC ending in Z")
    if lc is None:
        note("last_change absent")
        if lca is not None:
            err(GENERAL, "last_change_at without last_change")
    elif lc != "none" and lca is None:
        err(GENERAL, f"last_change {lc!r} needs last_change_at (it may be absent only with 'none')")
    changed_at = parse_utc(lca)
    if changed_at and published and changed_at > published:
        err(GENERAL, "last_change_at is later than published_at")

    # F2. Event start and end.
    es, ee = p.get("event_start"), p.get("event_end")
    for key, v in (("event_start", es), ("event_end", ee)):
        if v is not None and parse_utc(v) is None:
            err(GENERAL, f"{key}={v!r} is not ISO 8601 UTC ending in Z")
    tes, tee = parse_utc(es), parse_utc(ee)
    if tes and tee and tee < tes:
        err(GENERAL, "event_end is before event_start")
    prec = p.get("event_time_precision")
    if prec is not None:
        if prec not in vocab.enum("event_time_precision"):
            err(GENERAL, f"event_time_precision={prec!r} not in {sorted(vocab.enum('event_time_precision'))}")
        elif es is None and ee is None:
            err(GENERAL, "event_time_precision without event_start or event_end")
        else:
            for key, t in (("event_start", tes), ("event_end", tee)):
                if t and t != _floor(t, prec):
                    where = {"hour": "on the hour", "day": "at midnight UTC",
                             "month": "at midnight UTC on the 1st"}[prec]
                    err(GENERAL, f"event_time_precision {prec!r} needs {key} {where}")
    if es is None:
        note("event_start absent")

    # F3. Subject id.
    sid = p.get("subject_id")
    if sid is None:
        note("subject_id absent")
    elif not isinstance(sid, str) or not sid or any(ch.isspace() for ch in sid):
        err(GENERAL, "subject_id must be a non-empty string with no spaces")
    elif sid != p.get("id"):
        prog = p.get("program")
        if not SUBJECT_RE.match(sid) or (prog and not sid.startswith(f"{prog}:")):
            err(GENERAL, f"subject_id {sid!r} must equal the id or be shaped program:kind:key, starting '{prog}:'")
        elif DATED_RE.search(sid):
            note("subject_id carries a date: it names the thing read, not the reading")
        else:
            _check_zone_subject(sid, warn)

    # F4. Strength.
    sig = p.get("signal")
    if sig is not None:
        check_signal(sig, err)
    elif p.get("tier") == "anomaly":
        note("signal absent on an anomaly")
    br = p.get("baseline_ref")
    fr = br.get("flag_rate") if isinstance(br, dict) else None
    if fr is not None and (not _finite(fr) or not 0 <= fr <= 1):
        err("uncertainty", "baseline_ref.flag_rate must be a share from 0 to 1")
        fr = None

    # F5. Place.
    seas = p.get("sea_areas")
    if seas is None:
        if geom is not None:
            note("sea_areas absent on a placed item (use [] on land)")
    elif not isinstance(seas, list) or not all(isinstance(s, str) for s in seas):
        err(GENERAL, "sea_areas must be a list of sea-area slugs from geo/seas.json")
    else:
        from . import geo
        unknown = sorted(set(seas) - geo.sea_slugs())
        if unknown:
            err(GENERAL, f"sea_areas has slugs not in the kit's gazetteer (geo/seas.json): {unknown}")
    pb = p.get("place_basis")
    if pb is not None and pb not in vocab.enum("place_basis"):
        err(GENERAL, f"place_basis={pb!r} not in {sorted(vocab.enum('place_basis'))}")
    elif pb is None and p.get("countries"):
        note("place_basis absent on an item that names countries")
    if p.get("precision_class") is None:
        note("precision_class absent (required at revision 2.2)")
    elif p.get("precision_class") == "area" and isinstance(geom, dict) and geom.get("type") in ("Point", "MultiPoint"):
        note("precision_class 'area' drawn as a point: geometry is the true footprint")

    # F6. Lanes.
    for i, s in enumerate(p.get("sources") or []):
        if isinstance(s, dict) and s.get("lane") is not None and not (isinstance(s["lane"], str) and s["lane"]):
            err("sources", f"sources[{i}].lane must be the lane's key in the feed header's health (a non-empty string)")

    # F7. Corroboration (D11, kit 0.6.2). Shape only when present; no field marks an item as an event report, so
    # its absence is not noted.
    if p.get("corroboration") is not None:
        check_corroboration(p["corroboration"], published, err)

    # Tier anomaly, revision 2.1 (D5). Warnings only: each program adopts the rule as its own method version.
    if p.get("tier") == "anomaly":
        span = event_interval(p) if tee else None
        if span and span[1] and published and published - span[1] > timedelta(hours=HOLD_HOURS):
            # A measured window always closes before it is published, so "ended" is read as ended more than the
            # hold before publication (a cyclone that ended 13 days ago, still flagged).
            note(f"an anomaly whose event ended more than {HOLD_HOURS} hours before published_at: routine under "
                 "the 2.1 rule")
        if fr is not None and fr > FLAG_RATE_CAP:
            note(f"an anomaly whose baseline_ref.flag_rate is over {FLAG_RATE_CAP:.0%}: outside the 2.1 rule for a series")
        if sig is None and lc in ("none", "lowered", "changed", "ended"):
            note("an anomaly with no signal and no rise (last_change is not new or raised): outside the 2.1 rule")
        elif sig is None and lc in ("new", "raised") and changed_at and published \
                and published - changed_at > timedelta(hours=HOLD_HOURS):
            note(f"an anomaly with no signal, raised more than {HOLD_HOURS} hours ago: outside the 2.1 hold unless "
                 "the program states a longer one")


def check(item: dict, registers: dict | None = None, rev: str | None = None) -> list[tuple[str, str, str]]:
    """All problems with one item. registers (optional) holds the program's
    requirement, warning-problem and indicator ids for link checks. rev is the
    feed header's contract_rev: under "2.1" the tightened meaning of data_as_of
    is an error, otherwise a warning."""
    p, geom = split(item)
    out = []

    def err(std, msg):
        out.append((std, "error", msg))

    def warn(std, msg):
        out.append((std, "warning", msg))

    def one_of(std, key, allowed, required=True):
        v = p.get(key)
        if v is None:
            if required:
                err(std, f"{key} missing")
            return
        if v not in allowed:
            err(std, f"{key}={v!r} not in {sorted(allowed)}")

    def utc(std, key, required=True):
        v = p.get(key)
        if v is None:
            if required:
                err(std, f"{key} missing")
        elif not isinstance(v, str) or not UTC_RE.match(v):
            err(std, f"{key}={v!r} is not ISO 8601 UTC ending in Z")

    judged = is_judgment(p)

    # General contract fields.
    if p.get("contract") != CONTRACT:
        err(GENERAL, f"contract must be {CONTRACT!r}")
    for key in ("id", "program", "title"):
        if not p.get(key):
            err(GENERAL if key != "title" else "argumentation", f"{key} missing")
    one_of(GENERAL, "status", vocab.enum("status"))
    one_of(GENERAL, "msg_type", vocab.enum("msg_type"))
    one_of(GENERAL, "human_review", vocab.enum("human_review"))
    one_of(GENERAL, "us_person_data", vocab.enum("us_person_data"))  # a label for consumers, not a restriction
    utc("sources", "data_as_of")
    utc("sources", "published_at")
    utc(GENERAL, "valid_until", required=False)
    countries = p.get("countries")
    if countries is None:
        err(GENERAL, "countries missing (use [] for none)")
    elif not isinstance(countries, list) or any(not isinstance(c, str) or not COUNTRY_RE.match(c) for c in countries):
        err(GENERAL, "countries must be ISO 3166-1 alpha-2 codes (XK allowed)")
    subs = p.get("subdivisions")
    if subs is not None:
        if not isinstance(subs, list) or any(not isinstance(s, str) or not SUBDIVISION_RE.match(s) for s in subs):
            err(GENERAL, "subdivisions must be ISO 3166-2 codes such as US-HI")
        elif isinstance(countries, list) and any(s.split("-")[0] not in countries for s in subs):
            err(GENERAL, "each subdivision's country must also be in countries")
    if p.get("evidence_hash") is not None and not HASH_RE.match(str(p["evidence_hash"])):
        err(GENERAL, "evidence_hash must be 'sha256:' plus 64 hex digits")

    # Tags.
    for key, fw in (("ie_aspect", "ie_aspect"), ("pmesii_pt", "pmesii_pt"), ("ascope", "ascope")):
        v = p.get(key)
        if v is not None:
            allowed = set(vocab.framework(fw)["values"])
            bad = [x for x in (v if isinstance(v, list) else [v]) if x not in allowed]
            if bad:
                err(GENERAL, f"{key} has unknown values {bad}")
    if p.get("continuum") is not None and p["continuum"] not in vocab.framework("continuum")["values"]:
        err(GENERAL, f"continuum={p['continuum']!r} unknown")
    one_of(GENERAL, "product_category", vocab.enum("product_category"), required=False)
    one_of(GENERAL, "precision_class", vocab.enum("precision_class"), required=False)
    one_of("sources", "data_as_of_precision", vocab.enum("data_as_of_precision"), required=False)
    dap, asof = p.get("data_as_of_precision"), str(p.get("data_as_of") or "")
    if dap == "day" and not asof.endswith("T00:00:00Z"):
        err("sources", "data_as_of_precision 'day' needs data_as_of at midnight UTC (T00:00:00Z)")
    elif dap == "month" and not (asof.endswith("T00:00:00Z") and asof[8:10] == "01"):
        err("sources", "data_as_of_precision 'month' needs data_as_of at midnight UTC on the 1st")
    ncf_ids = p.get("ncf")
    if ncf_ids is not None:
        bad = [f for f in ncf_ids if f not in vocab.ncf()]
        if bad:
            err(GENERAL, f"ncf has unknown functions {bad}")
        elif p.get("sector") is not None and sorted(p["sector"]) != vocab.derive_sectors(ncf_ids):
            err(GENERAL, "sector does not match the sectors derived from ncf")
    for entry in p.get("lifeline") or []:
        if not isinstance(entry, dict) or entry.get("id") not in vocab.lifelines()["values"] \
                or entry.get("status") not in vocab.lifelines()["status"]:
            err(GENERAL, f"lifeline entry {entry!r} needs a known id and status")
    rs = p.get("response_stage")
    if rs is not None:
        ladder, _, value = str(rs).partition(":")
        if ladder not in vocab.ladders() or value not in vocab.ladders()[ladder]["values"]:
            err(GENERAL, f"response_stage={rs!r} is not 'ladder:value' from grading.json")

    # 1. Sources, data and method.
    sources = p.get("sources")
    if not sources:
        err("sources", "sources[] missing or empty")
    else:
        for i, s in enumerate(sources):
            for key in ("publisher", "licence"):
                if not s.get(key):
                    err("sources", f"sources[{i}].{key} missing")
            if not s.get("accessed_at") and not s.get("published_at"):
                warn("sources", f"sources[{i}] needs accessed_at or published_at (ICS 206-01)")
            if not (s.get("url") or s.get("id")):
                err("sources", f"sources[{i}] needs a url or a register id")
            if not s.get("descriptor"):
                warn("sources", f"sources[{i}].descriptor missing (ICS 206-01 source descriptor)")
            g = s.get("grade")
            if g is not None and not (isinstance(g, str) and len(g) == 2
                                      and g[0] in vocab.admiralty()["reliability"]
                                      and g[1] in vocab.admiralty()["credibility"]):
                err("sources", f"sources[{i}].grade={g!r} is not an Admiralty grade like 'B2'")
            if s.get("owner") is not None and s["owner"] not in vocab.source_owners():
                err("sources", f"sources[{i}].owner={s['owner']!r} not in {sorted(vocab.source_owners())}")
            persp = s.get("perspective")
            if persp is not None and not (isinstance(persp, str) and persp.strip()):
                err("sources", f"sources[{i}].perspective must be the program's source-group id (a non-empty string)")
        groups = {s.get("independence_group") or s.get("lineage_id") or s.get("id") or s.get("publisher")
                  for s in sources if isinstance(s, dict)}
        ones = [s.get("grade") for s in sources
                if isinstance(s, dict) and isinstance(s.get("grade"), str) and s["grade"][1:2] == "1"]
        if ones and len(groups) < 2:
            # Kit review M4 (kit 0.6.2): credibility 1 is "confirmed by other sources" (grading.json). A warning, so
            # feeds that grade a lone official notice A1 do not fail; the fix is A2.
            warn("sources", f"credibility 1 ({', '.join(sorted(set(ones)))}) means confirmed by other sources, and "
                            "this item rests on one independence group: grade it 2 at most")
    if not p.get("method_version"):
        err("sources", "method_version missing")
    cov = p.get("coverage_fraction")
    if cov is None:
        if p.get("indicator_state") != "no_data":
            warn("sources", "coverage_fraction missing")
    elif not isinstance(cov, (int, float)) or not 0 <= cov <= 1:
        err("sources", "coverage_fraction must be 0 to 1")

    # 2. Uncertainty.
    if judged:
        prob = p.get("probability")
        if prob is None:
            err("uncertainty", "a judgment needs probability (stored as a number)")
        else:
            try:
                expected = likelihood.term_for(prob)["id"]
                if p.get("likelihood_term") != expected:
                    err("uncertainty", f"likelihood_term should be {expected!r} for probability {prob}")
            except ValueError as e:
                err("uncertainty", str(e))
        one_of("uncertainty", "confidence", {"low", "moderate", "high"})
        if not p.get("confidence_basis"):
            err("uncertainty", "confidence_basis missing")
    if p.get("tier") == "anomaly" and not p.get("baseline_ref"):
        err("uncertainty", "an anomaly needs baseline_ref (baseline id, window, fixed or rolling)")

    # 3. Information versus judgment.
    one_of("distinguish", "kind", vocab.enum("kind"))
    one_of("distinguish", "tier", vocab.enum("tier"))
    one_of("distinguish", "status_class", vocab.enum("status_class"))
    if p.get("kind") == "observation" and p.get("tier") == "warning":
        err("distinguish", "an observation cannot be a warning: a warning is a judgment")
    if p.get("kind") in JUDGED_KINDS and p.get("tier") == "anomaly":
        err("distinguish", "an anomaly is a measurement: use kind=observation")
    actors = p.get("actors")
    if actors is not None:
        if isinstance(actors, list):
            _check_actors(actors, p, judged, err, warn)
        else:
            err(GENERAL, "actors must be a list")

    # 4. Alternatives.
    if judged:
        alts = p.get("alternatives") or []
        if not alts:
            err("alternatives", "a judgment needs alternatives[]")
        for i, a in enumerate(alts):
            if not a.get("hypothesis") or not a.get("tell_apart"):
                err("alternatives", f"alternatives[{i}] needs hypothesis and tell_apart (the indicator that separates it)")

    # 5. Relevance to a written requirement.
    linked = p.get("requirement_ids") or ([p["warning_problem_id"]] if p.get("warning_problem_id") else [])
    if not linked:
        (err if judged else warn)("relevance", "no requirement_ids or warning_problem_id")
    if registers:
        known = registers.get("requirements", set()) | registers.get("warning_problems", set())
        for r in linked:
            if r not in known:
                err("relevance", f"{r!r} is not in the program's requirements or warning problems")

    # 6. Argumentation.
    if judged and not p.get("summary"):
        err("argumentation", "a judgment needs a summary (bottom line up front)")
    if p.get("indicator_id"):
        if not p.get("hypothesis_id"):
            err("argumentation", "indicator_id without hypothesis_id")
        one_of("argumentation", "direction", vocab.enum("direction"))
        one_of("argumentation", "indicator_state", vocab.enum("indicator_state"))
        if registers and p["indicator_id"] not in registers.get("indicators", {p["indicator_id"]}):
            err("argumentation", f"indicator {p['indicator_id']!r} is not in indicators.json")

    # 7. Change.
    if judged:
        one_of("change", "change_from_prior", vocab.enum("change_from_prior"))
        if p.get("change_from_prior") not in (None, "new", "unchanged") and not p.get("change_reason"):
            err("change", "change_reason missing for a changed judgment")
    if p.get("msg_type") in ("update", "cancel", "error") and not p.get("supersedes"):
        err("change", f"msg_type={p['msg_type']} needs supersedes")

    # 8. Accuracy: scoreable forecasts.
    if p.get("kind") == "forecast":
        res = p.get("resolution") or {}
        for key in ("rule", "source", "resolve_by"):
            if not res.get(key):
                err("accuracy", f"forecast needs resolution.{key}")
        if not p.get("valid_until"):
            err("accuracy", "forecast needs valid_until")

    # 9. Visual first.
    vis = p.get("visual")
    if geom is None and not (isinstance(vis, dict) and vis.get("type") and vis.get("url")):
        err("visual", "no geometry and no visual {type, url}: a finding without a visual is not finished")
    if geom is None and p.get("precision_class") not in (None, "none", "country", "admin1"):
        err("visual", f"precision_class={p.get('precision_class')!r} but geometry is null")

    _check_revision(p, geom, rev == CONTRACT_REV, err, warn)
    return out
