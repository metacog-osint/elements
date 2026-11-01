"""Volcanoes: USGS volcano alert levels and aviation colour codes for US volcanoes.

The USGS Volcano Hazards Program lists every volcano above NORMAL or GREEN, with the previous level and the responsible
observatory's synopsis (US public domain). An empty list is a valid answer: no US volcano is elevated.

Not used: the Smithsonian Global Volcanism Program's daily report. Its site sits behind bot protection that refuses
scripted clients, and Elements does not work around that; its weekly RSS feed answers but ran two weeks behind its web
page on 31 Oct 2026. GDACS's orange and red volcano alerts cover the rest of the world for now."""
import json
import re

from .common import country_at, fetch_or_none

USGS_URL = "https://volcanoes.usgs.gov/vsc/api/volcanoApi/elevated"
ALERT_RANK = {"UNASSIGNED": -1, "NORMAL": 0, "ADVISORY": 1, "WATCH": 2, "WARNING": 3}
COLOR_RANK = {"UNASSIGNED": -1, "GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}
OBSERVATORIES = {"avo": "Alaska Volcano Observatory", "hvo": "Hawaiian Volcano Observatory",
                 "cvo": "Cascades Volcano Observatory", "yvo": "Yellowstone Volcano Observatory",
                 "calvo": "California Volcano Observatory", "nmi": "USGS, Northern Mariana Islands"}


def _utc(s) -> str | None:
    """USGS writes '2026-10-31 20:36:30' in UTC."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", str(s or ""))
    return f"{m.group(1)}T{m.group(2)}Z" if m else None


def parse_usgs(doc) -> list[dict]:
    out = []
    for v in doc if isinstance(doc, list) else []:
        try:
            lat, lon = float(v["lat"]), float(v["long"])
        except (KeyError, TypeError, ValueError):
            lat = lon = None
        obs = (v.get("obs") or "").lower()
        cc = country_at(lat, lon) if lat is not None else None
        out.append({"vnum": str(v.get("vnum") or ""), "name": v.get("vName") or "", "observatory": obs,
                    "observatory_name": OBSERVATORIES.get(obs, obs.upper()),
                    "alert": (v.get("alertLevel") or "").upper() or None, "color": (v.get("colorCode") or "").upper() or None,
                    "prev_alert": (v.get("alertLevelPrev") or "").upper() or None,
                    "prev_color": (v.get("colorCodePrev") or "").upper() or None,
                    "sent": _utc(v.get("sentUtc")), "changed": _utc(v.get("codeChangeDate")),
                    "synopsis": " ".join((v.get("noticeSynopsis") or "").split()), "url": v.get("noticeUrl"),
                    "threat": v.get("nvewsThreat"), "lat": lat, "lon": lon,
                    # USGS observes US volcanoes; seamounts at sea get the territory the observatory covers
                    "countries": [cc] if cc else (["MP"] if obs == "nmi" else ["US"])})
    return out


def collect_usgs(old, fetch=fetch_or_none):
    body, err = fetch(USGS_URL, 40)
    if body is None:
        return old or [], err
    if not body.strip():
        return old or [], "empty answer"
    try:
        return parse_usgs(json.loads(body)), None
    except ValueError as e:
        return old or [], f"parse: {e}"


def change(rec: dict) -> str | None:
    """'raised' or 'lowered' when the alert (or, failing that, the colour) moved from its previous value. UNASSIGNED
    (a volcano without ground monitoring) counts as below NORMAL."""
    if not rec.get("prev_alert") and not rec.get("prev_color"):
        return None
    a = ALERT_RANK.get(rec.get("alert") or "", 0) - ALERT_RANK.get(rec.get("prev_alert") or "", 0)
    c = COLOR_RANK.get(rec.get("color") or "", 0) - COLOR_RANK.get(rec.get("prev_color") or "", 0)
    d = a or c
    return "raised" if d > 0 else "lowered" if d < 0 else None
