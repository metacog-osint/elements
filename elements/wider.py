"""Wider collection (decision of 19 Nov 2026): lanes kept for the record, outside the feed's tiers.

Nothing here reaches the feed, the map or an anomaly. Each lane appends to its own folder, one line per message or
change, in history/<lane>/YYYY-MM-DD.jsonl for the UTC day of the run; a finished day is gzipped once and never written
again (meteoalarm_log.close_days). A lane that fails writes nothing and never stops the run.

- nws_minor: every NWS alert message rated Moderate or Minor (the feed keeps Severe and Extreme). Read by issue time
  since the last complete read, so an alert issued and ended between two runs is kept. The long description and
  instruction text are left out for size; `url` is the message at api.weather.gov. US public domain.
- gdacs_green_wildfires: GDACS green wildfire events (the feed takes orange and red only). One line when first seen and
  again when the event changes. Read page by page, because GDACS returns at most 100 events a query. Source: GDACS
  (EC Joint Research Centre and UN OCHA).

Low-confidence FIRMS cells are the third lane. They are hourly cells, so they go to the monthly release beside the
main cells (firms_store.py), not to git."""
import json
from datetime import datetime, timedelta
from pathlib import Path

from . import meteoalarm_log, sources, weather
from .common import fetch_or_none

NWS_FORMAT = "elements-nws-minor/1"
GDACS_FORMAT = "elements-gdacs-green-wildfire/1"
NWS_URL = ("https://api.weather.gov/alerts?status=actual&message_type=alert,update&severity=Moderate,Minor"
           "&limit=500&start={start}")
NWS_PAGES = 12          # 500 messages a page; a first read of 72 hours is about 4,000
NWS_MAX_H = 72
NWS_SEEN_DAYS = 5       # longer than the read-back, so a message is never logged twice
GDACS_PAGES = 12        # 100 events a page; 14 days held 438 on 23 Nov 2026
GDACS_DAYS = 14
GDACS_SEEN_DAYS = 45    # an event still listed is compared with its last logged line
GDACS_KEYS = ("id", "episode", "name", "alert", "latest_alert", "score", "severity", "severity_value", "severity_unit",
              "from", "to", "current", "country", "countries", "report", "lon", "lat")
GDACS_CHANGE = ("episode", "alert", "latest_alert", "score", "severity_value", "to", "current")


def _stamp(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _recent(root: Path, today: datetime, days: int) -> list:
    """The lines of the lane's last `days` day files, oldest first."""
    first = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    out = []
    for p in sorted(Path(root).glob("*.jsonl*")):
        if p.name[:10] >= first:
            out += meteoalarm_log.read_all_file(p)
    return out


def _append(root: Path, lines: list, day: str) -> None:
    root = Path(root)
    if lines:
        root.mkdir(parents=True, exist_ok=True)
        # A closed day is never reopened: if today's file was already gzipped (a clock set back), write beside it.
        p = root / f"{day}.jsonl" if not (root / f"{day}.jsonl.gz").exists() else root / f"{day}.late.jsonl"
        with p.open("a", encoding="utf-8", newline="\n") as fh:
            for x in lines:
                fh.write(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n")
    if root.exists():
        meteoalarm_log.close_days(root, day)


# ---- NWS Moderate and Minor --------------------------------------------------------------------------------------
def nws_line(feature: dict, at: str) -> dict | None:
    p = feature.get("properties") or {}
    if p.get("severity") not in ("Moderate", "Minor") or not p.get("id"):
        return None
    params, codes = p.get("parameters") or {}, p.get("geocode") or {}
    return {"format": NWS_FORMAT, "at": at, "id": weather._oid_tail(p["id"]), "sent": weather._utc(p.get("sent")),
            "effective": weather._utc(p.get("effective")), "onset": weather._utc(p.get("onset")),
            "expires": weather._utc(p.get("expires")), "ends": weather._utc(p.get("ends")),
            "type": p.get("messageType"), "event": p.get("event"), "severity": p.get("severity"),
            "urgency": p.get("urgency"), "certainty": p.get("certainty"), "sender": p.get("senderName"),
            "headline": p.get("headline"), "areas": p.get("areaDesc"), "ugc": codes.get("UGC") or [],
            "vtec": params.get("VTEC") or [],
            "references": [weather._oid_tail(r.get("identifier")) for r in p.get("references") or []
                           if isinstance(r, dict) and r.get("identifier")],
            "geometry": weather._round_geom(feature.get("geometry")), "url": p.get("@id")}


def nws_start(root: Path, now: datetime) -> str:
    """An hour before the last complete read, no further back than NWS_MAX_H hours."""
    last = None
    try:
        last = weather._parse(json.loads((Path(root) / "state.json").read_text(encoding="utf-8")).get("last_complete"))
    except (OSError, ValueError, AttributeError):
        pass
    floor = now - timedelta(hours=NWS_MAX_H)
    return _stamp(max(last - timedelta(hours=1), floor) if last else floor)


def update_nws(root: Path, now: datetime, fetch=fetch_or_none) -> str:
    root, at = Path(root), _stamp(now)
    url, feats, pages, problem = NWS_URL.format(start=nws_start(root, now)), [], 0, None
    while url and pages < NWS_PAGES:
        body, err = fetch(url, 60)
        try:
            doc = json.loads(body) if body is not None else None
        except ValueError as e:
            doc, err = None, f"parse: {e}"
        if doc is None:
            problem = f"page {pages + 1}: {err}"
            break
        pages += 1
        got = doc.get("features") or []
        feats += got
        nxt = (doc.get("pagination") or {}).get("next")
        url = nxt if got and nxt and nxt != url else None
    if url and not problem:
        problem = f"stopped at {NWS_PAGES} pages"
    if problem and not feats:
        return f"nws minor: {problem}"
    seen = {x.get("id") for x in _recent(root, now, NWS_SEEN_DAYS)}
    lines = []
    for f in feats:
        line = nws_line(f, at)
        if line and line["id"] not in seen:
            seen.add(line["id"])
            lines.append(line)
    lines.sort(key=lambda x: (x["sent"] or "", x["id"]))
    _append(root, lines, at[:10])
    if not problem:   # a partial read leaves the start where it was, so the next run reads the rest
        root.mkdir(parents=True, exist_ok=True)
        (root / "state.json").write_text(json.dumps({"format": NWS_FORMAT, "last_complete": at}) + "\n",
                                         encoding="utf-8", newline="\n")
    return f"nws minor: {len(lines)} new messages" + (f" (partial: {problem})" if problem else "")


# ---- GDACS green wildfires ---------------------------------------------------------------------------------------
def gdacs_url(now: datetime, page: int) -> str:
    frm, to = (now - timedelta(days=GDACS_DAYS)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
    return (f"{sources.GDACS_API}?fromdate={frm}&todate={to}&eventlist=WF&alertlevel=Green"
            f"&pagesize=100&pagenumber={page}")


def update_gdacs(root: Path, now: datetime, fetch=fetch_or_none) -> str:
    root, at = Path(root), _stamp(now)
    events, problem, page = {}, None, 1
    while page <= GDACS_PAGES:
        body, err = fetch(gdacs_url(now, page), 60)
        if body is None:
            problem = f"page {page}: {err}"
            break
        if not body.strip():    # GDACS answers an empty body past the last page
            break
        try:
            doc = json.loads(body)
            got = sources.parse_gdacs(doc)
        except ValueError as e:
            problem = f"page {page}: parse: {e}"
            break
        for e in got:
            if e.get("type") == "WF" and e.get("alert") == "green":
                events[e["id"]] = e
        if len(doc.get("features") or []) < 100:   # the raw count: parse_gdacs skips events without a point
            break
        page += 1
    else:
        problem = f"stopped at {GDACS_PAGES} pages"
    if problem and not events:
        return f"gdacs green wildfires: {problem}"
    last = {x.get("id"): x for x in _recent(root, now, GDACS_SEEN_DAYS)}
    lines = []
    for key in sorted(events):
        e, prev = events[key], last.get(key)
        if prev and all(prev.get(k) == e.get(k) for k in GDACS_CHANGE):
            continue
        line = {"format": GDACS_FORMAT, "at": at, "change": "changed" if prev else "new"}
        line.update({k: e.get(k) for k in GDACS_KEYS})
        lines.append(line)
    _append(root, lines, at[:10])
    return f"gdacs green wildfires: {len(lines)} new or changed of {len(events)}" + (
        f" (partial: {problem})" if problem else "")


def update_all(hist: Path, now: datetime, fetch=fetch_or_none) -> list:
    """One line per lane. A lane that raises is reported and the other still runs."""
    out = []
    for name, fn, folder in (("nws minor", update_nws, "nws_minor"),
                             ("gdacs green wildfires", update_gdacs, "gdacs_green_wildfires")):
        try:
            out.append(fn(Path(hist) / folder, now, fetch))
        except Exception as e:  # noqa: BLE001 - a record-keeping lane must never stop the site's run
            out.append(f"{name}: failed: {type(e).__name__}: {e}")
    return out
