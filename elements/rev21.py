"""Feed contract revision 2.1 (kit 0.6.4) for Elements: subjects, change flags, event times, place basis, sea areas,
signals and corroboration (feed-contract migration step 4.3, 19 Nov 2026).

The builders in feed.py keep their items as before; finish() adds the 2.1 fields from what each item already carries
(its lane, measures and data_as_of), then fills last_change from the history log where the item does not state it.

Decisions (Tom, 19 Nov 2026, "Take the Elements defaults too"):
- An NWS alert without VTEC is one subject along its CAP chain (weather.py keys it on the chain's first message, as
  MeteoAlarm does), so an update is a change, not a new alert and an end.
- A USGS earthquake that EMSC also locates, from a solution that is not USGS's own (authority other than NEIC), is
  corroborated by two independent origins. first_reported_at is the origin time (neither catalogue gives the time it
  first published); corroborated_at is the later of the two catalogues' last-update times, the time by which both had
  reported. Unmatched quakes carry no corroboration.
- The US Drought Monitor's map is raised or lowered when the area in severe drought or worse (D2-D4, cumulative) moves
  by more than 1 percentage point week on week; a smaller move reads none (standing).
Every item's subject is its id: Elements' ids already name the thing read (an event, a warning chain, a volcano, a
country), never the run that read it.
"""
from datetime import datetime, timedelta, timezone

from . import common  # noqa: F401  (first: puts the doctrine kit on sys.path)
from tic_doctrine import contract, geo, history  # noqa: E402

STALE_HOURS = 48      # a source with no good read for this long is stale (COP's stale_hours for Elements)
USDM_POINTS = 1.0     # percentage points of US area in D2-D4 that make a weekly move raised or lowered
RULE = "corroborate-1: two independent origins, or one official source within its remit"

ALERT_RANK = {"UNASSIGNED": 0, "NORMAL": 0, "ADVISORY": 1, "WATCH": 2, "WARNING": 3}
COLOR_RANK = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}
PAGER_RANK = {"green": 1, "yellow": 2, "orange": 3, "red": 4}
GDACS_RANK = {"green": 1, "orange": 2, "red": 3}
CAP_RANK = {"Minor": 1, "Moderate": 2, "Severe": 3, "Extreme": 4}
TSUNAMI_RANK = {"information": 1, "threat": 2, "advisory": 3, "watch": 3, "warning": 4}


def _utc(s) -> str | None:
    """s as ISO 8601 UTC ending in Z (seconds), or None when it is not a time the kit reads."""
    t = contract.parse_utc(s) if isinstance(s, str) else None
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def _midnight(s) -> str | None:
    t = _utc(s) or _utc(f"{s}T00:00:00Z" if isinstance(s, str) and len(s) == 10 else None)
    return f"{t[:10]}T00:00:00Z" if t else None


def lane(p: dict) -> str:
    return p["id"].split(":")[1]


def event(p: dict, start, end=None, precision: str | None = None) -> None:
    start, end = _utc(start), _utc(end)
    if not start:
        return
    p["event_start"] = start
    if end and end >= start:
        p["event_end"] = end
    if precision:
        p["event_time_precision"] = precision


def signal(p: dict, name: str, value, unit: str) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        p["signal"] = {"name": name, "value": value, "unit": unit}


def stamp(p: dict, change: str, at) -> None:
    at = _utc(at)
    if change == "none":
        p["last_change"] = "none"
    elif at:
        p["last_change"], p["last_change_at"] = change, at


def corroboration(q: dict, e: dict) -> dict | None:
    """Two independent catalogues (USGS and EMSC, not NEIC) report one earthquake (decision 2)."""
    first = _utc(q.get("time"))
    later = max(x for x in (_utc(q.get("updated")), _utc(e.get("updated")), first) if x) if first else None
    if not first:
        return None
    return {"state": "corroborated", "basis": "origins", "origins": 2, "official": None, "party_claim": False,
            "first_reported_at": first, "corroborated_at": later, "rule": RULE}


def usdm_change(m: dict) -> str:
    """Decision 3: raised or lowered past USDM_POINTS of D2-D4 area, else none."""
    d = m.get("change_d2")
    if isinstance(d, (int, float)) and abs(d) > USDM_POINTS:
        return "raised" if d > 0 else "lowered"
    return "none"


def _lane_fields(p: dict) -> None:
    """Event times, signals and stated changes, per lane, from fields the builders already parsed."""
    m, kind = p.get("measures") or {}, lane(p)
    if kind in ("usgs", "emsc"):
        event(p, p.get("data_as_of"))                      # the origin time
        if kind == "usgs" and m.get("pager") in PAGER_RANK:
            signal(p, "USGS PAGER alert level", PAGER_RANK[m["pager"]], "level (1 green to 4 red)")
    elif kind == "gdacs":
        # A current event's 'to' is its latest report, not an end: only a finished event gets one.
        event(p, m.get("from"), None if m.get("current") else m.get("to"))
        alert = (p.get("response_stage") or "").split(":")[-1]
        if alert in GDACS_RANK:
            signal(p, "GDACS alert level", GDACS_RANK[alert], "level (1 green to 3 red)")
    elif kind == "cems":
        event(p, m.get("event"))
    elif kind == "usgs-volcano":
        a, c = (m.get("alert_level") or "").upper(), (m.get("aviation_color") or "").upper()
        if a in ALERT_RANK and a not in ("UNASSIGNED",):
            signal(p, "USGS volcano alert level", ALERT_RANK[a], "level (0 normal to 3 warning)")
        elif c in COLOR_RANK:
            signal(p, "USGS aviation colour code", COLOR_RANK[c], "level (0 green to 3 red)")
        if m.get("change") in ("raised", "lowered"):
            stamp(p, m["change"], m.get("changed_at") or p.get("data_as_of"))
    elif kind == "nws":
        event(p, m.get("onset"), m.get("ends"))
        signal(p, "CAP severity", CAP_RANK.get(m.get("severity")), "level (1 minor to 4 extreme)")
    elif kind == "spc":
        event(p, m.get("valid"), m.get("expires"))
        signal(p, "SPC categorical risk", m.get("level"), "level (1 marginal to 5 high)")
    elif kind == "tsunami":
        event(p, m.get("origin"))
        signal(p, "NOAA tsunami message level", TSUNAMI_RANK.get(m.get("level")), "level (1 information to 4 warning)")
    elif kind == "usdm":
        event(p, _midnight(m.get("map_date")), _midnight(m.get("valid_end")), "day")
        signal(p, "US area in severe drought or worse (D2-D4)", m.get("d2"), "percent of US area")
        stamp(p, usdm_change(m), _midnight(m.get("map_date")))
    elif kind == "meteoalarm":
        if p["id"].endswith(":in-force"):
            return                                         # a count of warnings in force: no one event
        event(p, m.get("onset"), m.get("expires"))
        signal(p, "MeteoAlarm awareness level", m.get("level"), "level (2 yellow to 4 red)")
    elif kind == "nifc":
        event(p, m.get("discovered"))
    elif kind == "firms":
        event(p, m.get("window_start"), m.get("window_end"))
        signal(p, "VIIRS fire and heat detections, past 24 hours", m.get("detections"), "detections")


def regrade(p: dict) -> None:
    """Kit 0.6.2: credibility 1 means confirmed by other sources, so an item resting on one independence group grades
    its sources 2 at most (A1 becomes A2). An earthquake that EMSC independently locates keeps USGS's A1."""
    src = p.get("sources") or []
    if len({s.get("independence_group") for s in src if s.get("independence_group")}) >= 2:
        return
    for s in src:
        g = s.get("grade") or ""
        if len(g) == 2 and g[1] == "1":
            s["grade"] = g[0] + "2"


def health_states(health: dict, newest: dict, now: datetime) -> dict:
    """The feed header's health with each lane's 2.1 state and data_as_of (its newest item). A copy: data/health.json,
    which the history step reads, is left as it is."""
    cutoff = (now - timedelta(hours=STALE_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {}
    for k, e in (health or {}).items():
        e = dict(e)
        ok, checked = e.get("last_ok"), e.get("checked_at")
        e["state"] = ("never" if not ok else "fresh" if ok == checked else "stale" if ok < cutoff else "failing")
        e.setdefault("last_error", None)
        e.setdefault("failures", 0)
        if newest.get(k) and not e.get("data_as_of"):
            e["data_as_of"] = newest[k]
        out[k] = e
    return out


def finish(feats: list[dict], state: dict | None = None, since: str | None = None) -> None:
    """Add the 2.1 fields to every item. With the history state (after this run's history step), fill last_change on
    the items that do not state it; a filled time is never later than the item's publication."""
    seas = {}
    for f in feats:
        p = f["properties"]
        p.setdefault("subject_id", p["id"])
        _lane_fields(p)
        regrade(p)
        if p.get("countries"):
            p["place_basis"] = "location"                  # every Elements hazard is where it names
        g = f.get("geometry")
        if g and p.get("precision_class") == "country":
            p["sea_areas"] = []                            # a country's label point stands for the country
        elif g:
            key = repr(g)
            if key not in seas:
                seas[key] = geo.sea_areas_for_geometry(g)
            p["sea_areas"] = list(seas[key])
    if state is not None:
        history.fill_last_change({"features": feats}, state, since)
    for f in feats:
        p = f["properties"]
        if p.get("last_change_at") and p["last_change_at"] > p["published_at"]:
            p["last_change_at"] = p["published_at"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
