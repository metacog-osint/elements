"""US nuclear power reactors and fuel facilities, from the US Nuclear Regulatory Commission (method elements-feed-1.2,
26 Nov 2026). Two lanes:

- nrc-events: the NRC Operations Center's Event Notification Reports, one page per business day. Each event is a
  licensee's report, with the emergency class the licensee declared (Non Emergency, Notification of Unusual Event,
  Alert, Site Area Emergency, General Emergency). Elements reads the newest REPORTS pages each run and keeps every
  event for KEEP_DAYS; the feed carries power reactor and fuel cycle facility events from the last SHOW_DAYS.
- nrc-reactor-status: the NRC's daily Power Reactor Status Report, each unit's power as a percentage of full, as the
  licensee reported it between 4 and 8 a.m. Eastern. Read from the year's pipe-delimited file (newest date first), of
  which only the first STATUS_BYTES are read; KEEP_DATES report dates are kept.

The NRC states both are unevaluated information from the licensees, and neither gives a reason for a power level.
Elements reports the NRC's numbers and classes as they stand and names no cause. Personal names on the event pages
(who notified whom) are not read.

Units are placed from catalog/us_reactors.json (FEMA's reactor locations, tools/build_reactors.py)."""
import html
import json
import re
from datetime import datetime, timedelta, timezone
from functools import cache

from .common import ROOT, fetch_or_none, fetch_start

BASE = "https://www.nrc.gov/documents-reports/document-collections/events-reports-associated-with"
EVENTS_INDEX = BASE + "/event-notification-reports/{year}"
EVENTS_REPORT = BASE + "/event-notification-reports/{year}/{ymd}en"
STATUS_FILE = BASE + "/power-reactor-status-reports/{year}/{year}PowerStatus.txt"
STATUS_PAGE = BASE + "/power-reactor-status-reports/{year}/{ymd}ps"
REPORTS = 5            # newest event reports read each run (about a business week)
KEEP_DAYS = 30         # events kept in data/nrc_events.json, by notification time
SHOW_DAYS = 7          # events in the feed, by notification time
FEED_TYPES = ("Power Reactor", "Fuel Cycle Facility")
STATUS_BYTES = 200_000  # the year file's first ~45 report dates (95 units a day, ~45 bytes a line)
KEEP_DATES = 31        # status report dates kept
SHUTDOWN_FROM = 20     # a unit reported at 0% after a report of this much power or more counts as a shutdown
BASELINE_MIN = 7       # earlier day pairs a unit needs before its shutdown can be an anomaly
HOLD_HOURS = 72        # contract 2.1's hold (D5)
FLAG_RATE_CAP = 0.05   # contract 2.1: a series rule that flags more than 5% of its baseline is not one

# The NRC's emergency classes (10 CFR 50.72 and Part 50 Appendix E), lowest to highest, in the reports' own words
# (an "Unusual Event" is a Notification of Unusual Event).
CLASSES = [("non_emergency", "Non Emergency"), ("unusual_event", "Unusual Event"), ("alert", "Alert"),
           ("site_area_emergency", "Site Area Emergency"), ("general_emergency", "General Emergency")]
CLASS_WORDS = {"nonemergency": 0, "unusualevent": 1, "notificationofunusualevent": 1, "alert": 2,
               "siteareaemergency": 3, "generalemergency": 4}
ZONES = {"EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6, "PST": -8, "PDT": -7, "AKST": -9,
         "AKDT": -8, "HST": -10, "UTC": 0, "GMT": 0}
DST_ZONES = {"ET": (-5, -4), "CT": (-6, -5), "MT": (-7, -6), "PT": (-8, -7)}
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BLOCK = re.compile(r'<div class="grid border" id="en(\d+)">')
FIELD = re.compile(r"<b>\s*([^<:]+?)\s*:\s*</b>([^<]*)")
RETRACTED = re.compile(r"\*\s*\*\s*\*\s*RETRACT", re.I)
TERMINATED = re.compile(r"\bterminat\w*\b[^.]{0,80}?\b(unusual event|alert|site area emergency|general emergency|"
                        r"emergency)", re.I)
UPDATE = re.compile(r"\*\s*\*\s*\*\s*UPDATE", re.I)
STOP_WORDS = {"nuclear", "generating", "station", "power", "plant", "unit", "units", "npp"}
ACRONYMS = {"rps", "eccs", "hpci", "rcic", "esf", "edg", "edgs", "loca", "nrc", "heu", "leu", "isfsi", "tsc", "eof",
            "hpcs", "rhr", "ffd", "pwr", "bwr", "ler", "eal", "spds", "ac", "dc", "msiv", "rwcu", "esfas", "aux",
            "ups", "hvac", "cfr", "rcs", "sg", "afw", "nsss", "ii", "iii", "iv", "us", "noue", "ue"}


# ---- times ------------------------------------------------------------------------------------------------------
def _nth_sunday(year: int, month: int, n: int) -> datetime:
    d = datetime(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _us_dst(local: datetime) -> bool:
    """US daylight time (2007 rule): from 2 a.m. on the second Sunday of March to 2 a.m. on the first Sunday of
    November, local time."""
    start = _nth_sunday(local.year, 3, 2).replace(hour=2)
    end = _nth_sunday(local.year, 11, 1).replace(hour=2)
    return start <= local < end


def to_utc(date: str, time: str, zone: str) -> str | None:
    """'02/23/2026', '03:02', 'ET' -> '2026-02-23T08:02:00Z'. ET (CT, MT, PT) follows US daylight time; EST and the
    other fixed zones do not. None for a zone or time Elements cannot read."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", date or "")
    t = re.match(r"\s*(\d{1,2}):?(\d{2})", time or "")
    if not m or not t:
        return None
    try:
        local = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), int(t.group(1)) % 24, int(t.group(2)))
    except ValueError:
        return None
    z = (zone or "").strip().upper()
    if z in DST_ZONES:
        off = DST_ZONES[z][1] if _us_dst(local) else DST_ZONES[z][0]
    elif z in ZONES:
        off = ZONES[z]
    else:
        return None
    return (local - timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mdy(s: str) -> str | None:
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


# ---- event notification reports ----------------------------------------------------------------------------------
def _text(s: str) -> str:
    return " ".join(CTRL.sub(" ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).split())


def emergency_class(raw: str):
    """(code, level 0-4, NRC name) for an Emergency Class field; (None, None, raw) when it is not one Elements knows."""
    key = re.sub(r"[^a-z]", "", (raw or "").lower())
    if key in CLASS_WORDS:
        code, name = CLASSES[CLASS_WORDS[key]]
        return code, CLASS_WORDS[key], name
    return None, None, _text(raw) or None


def parse_index(doc: str) -> list[str]:
    """Report dates (YYYYMMDD) linked from a year's index page, newest first."""
    return sorted(set(re.findall(r"event-notification-reports/\d{4}/(\d{8})en", doc or "")), reverse=True)


def _unit_table(chunk: str) -> list[dict]:
    m = re.search(r"<caption>\s*Power Reactor Unit Info\s*</caption>(.*?)</table>", chunk, re.S | re.I)
    if not m:
        return []
    keys = ("unit", "scram_code", "critical", "initial_power", "initial_mode", "current_power", "current_mode")
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= len(keys):
            r = dict(zip(keys, cells))
            for k in ("initial_power", "current_power"):
                r[k] = int(r[k]) if r[k].isdigit() else None
            rows.append(r)
    return rows


def parse_report(doc: str, ymd: str) -> list[dict]:
    """The events on one day's report page. Each event's own fields, its unit table, the first line of its text (the
    NRC's headline), and whether the text reports a retraction or an emergency terminated. Not the rest of the text,
    and no personal names."""
    doc = CTRL.sub(" ", doc or "")
    starts = [(m.start(), m.group(1)) for m in BLOCK.finditer(doc)]
    url = EVENTS_REPORT.format(year=ymd[:4], ymd=ymd)
    out = []
    for i, (pos, number) in enumerate(starts):
        chunk = doc[pos:starts[i + 1][0] if i + 1 < len(starts) else len(doc)]
        head, _, body = chunk.partition("<b>Event Text</b>")
        th = re.findall(r'<div class="th">(.*?)</div>', head, re.S)
        f = {}
        for k, v in FIELD.findall(head):
            f.setdefault(_text(k), _text(v))
        cfr = re.search(r"10 CFR Section:\s*<br\s*/?>(.*?)</div>", head, re.S | re.I)
        text = re.search(r'<div class="border">(.*?)</div>', body, re.S)
        text = text.group(1) if text else ""
        first = _text(re.split(r"<br\s*/?>", text, maxsplit=1)[0])
        code, level, cls = emergency_class(f.get("Emergency Class"))
        units = re.findall(r"\[(\d+)\]", f.get("Unit") or "")
        nd, nt = f.get("Notification Date"), (f.get("Notification Time") or "")
        ed, et = f.get("Event Date"), (f.get("Event Time") or "")
        zone = lambda s: (re.search(r"\[([A-Z]+)\]", s) or [None, None])[1]  # noqa: E731
        kind = _text(th[0]) if th else None
        out.append({
            "number": int(number), "type": kind,
            "facility": f.get("Facility") or None, "licensee": f.get("Licensee") or None, "rep_org": f.get("Rep Org") or None,
            "region": f.get("Region") or None, "state": (f.get("State") or "").upper() or None,
            "city": f.get("City") or None, "county": f.get("County") or None, "docket": f.get("Docket") or None,
            "units": units, "rx_type": f.get("RX Type") or None,
            "notified": to_utc(nd, nt, zone(nt)), "event_time": to_utc(ed, et, zone(et)),
            "updated_on": _mdy(f.get("Last Update Date")), "emergency_class": cls, "class_code": code, "level": level,
            "cfr": (_text(cfr.group(1)) if cfr else None) or None, "unit_info": _unit_table(head),
            "headline": first or None, "retracted": bool(RETRACTED.search(text)),
            "terminated": bool(TERMINATED.search(_text(text))), "updates": len(UPDATE.findall(text)),
            "report": ymd, "url": f"{url}#en{number}"})
    return out


def _newer(a: dict, b: dict) -> bool:
    """Whether a is a later reading of the same event than b."""
    return (a.get("updated_on") or "", a.get("report") or "") >= (b.get("updated_on") or "", b.get("report") or "")


def collect_events(old, now: datetime | None = None, fetch=fetch_or_none):
    """(records, problem). The newest REPORTS report pages, merged with the kept events by number. A failed index or
    every failed page keeps the earlier records (and says so: the source was not read)."""
    now = now or datetime.now(timezone.utc)
    when = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    years = [now.year] + ([now.year - 1] if now.month == 1 else [])
    dates, problems = [], []
    for y in years:
        body, err = fetch(EVENTS_INDEX.format(year=y), 40)
        if body is None:
            problems.append(f"{y} index: {err}")
            continue
        dates += parse_index(body.decode("utf-8", "replace"))
    if not dates:
        return old or [], "every index failed: " + "; ".join(problems) if problems else "no reports listed"
    records = {r["number"]: r for r in old or []}
    read = 0
    for ymd in sorted(set(dates), reverse=True)[:REPORTS]:
        body, err = fetch(EVENTS_REPORT.format(year=ymd[:4], ymd=ymd), 40)
        if body is None:
            problems.append(f"report {ymd}: {err}")
            continue
        events = parse_report(body.decode("utf-8", "replace"), ymd)
        if not events and "Event Number" not in body.decode("utf-8", "replace"):
            problems.append(f"report {ymd}: no events found")
            continue
        read += 1
        for e in events:
            prev = records.get(e["number"])
            if prev and not _newer(e, prev):
                continue
            if prev and (e.get("level") or 0) > (prev.get("level") or 0):
                e["raised_at"] = when            # a later report raised the class Elements had read
            elif prev and prev.get("raised_at"):
                e["raised_at"] = prev["raised_at"]
            records[e["number"]] = e
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = sorted((r for r in records.values() if (r.get("notified") or f"{r['report'][:4]}-{r['report'][4:6]}-"
                                                   f"{r['report'][6:]}T00:00:00Z") >= cutoff),
                 key=lambda r: (r.get("notified") or "", r["number"]), reverse=True)
    if not read:
        return out, "every report failed: " + "; ".join(problems)
    return out, ("; ".join(problems) or None)


# ---- power reactor status ----------------------------------------------------------------------------------------
def parse_status(text: str, cut: bool = False) -> dict:
    """{'2026-11-25': {unit: power}} from the year file's lines (ReportDt|Unit|Power). When the read was cut, the last
    line and the oldest date (both perhaps partial) are dropped."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if cut and lines:
        lines = lines[:-1]
    out = {}
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not parts[2].lstrip("-").isdigit():
            continue
        day = _mdy(parts[0])
        if day and parts[1]:
            out.setdefault(day, {})[" ".join(parts[1].split())] = int(parts[2])
    if cut and out:
        out.pop(min(out))
    return out


def collect_status(old, now: datetime | None = None, fetch=fetch_start):
    """(records, problem): records [{'date', 'units': {unit: power}}], newest first, KEEP_DATES of them. Reads the
    year's file, and last year's when the new year has fewer dates than that (or no file yet)."""
    now = now or datetime.now(timezone.utc)
    days = {r["date"]: r["units"] for r in old or []}
    problems, read = [], 0
    for y in (now.year, now.year - 1):
        body, cut, err = fetch(STATUS_FILE.format(year=y), STATUS_BYTES)
        if body is None:
            problems.append(f"{y} file: {err}")
            if y == now.year and err == "HTTP 404" and now.month == 1:
                continue                     # no file for the new year yet
            if y == now.year:
                break
            continue
        got = parse_status(body.decode("utf-8", "replace"), cut)
        if not got:
            problems.append(f"{y} file: no report lines")
            break
        read += 1
        days.update(got)
        if y == now.year and (len(got) >= KEEP_DATES or now.month > 1):
            break
    if not read:
        return old or [], "every file failed: " + "; ".join(problems)
    return [{"date": d, "units": days[d]} for d in sorted(days, reverse=True)[:KEEP_DATES]], ("; ".join(problems) or None)


def assess(records: list[dict], now: datetime) -> list[dict]:
    """Per unit on the newest report: its power, the one before, and its latest change in the store (the run of reports
    at its present power and what came before it). Units steady at 100% are left out unless they just changed. A
    shutdown is a unit at 0% after a report of SHUTDOWN_FROM% or more; it is an anomaly when that report is within
    HOLD_HOURS, the unit is still at 0%, and the unit's own earlier day pairs (BASELINE_MIN or more) show such
    shutdowns on no more than FLAG_RATE_CAP of them."""
    if not records:
        return []
    newest = records[0]
    hold = (now - timedelta(hours=HOLD_HOURS)).strftime("%Y-%m-%d")
    out = []
    for unit, power in sorted(newest["units"].items()):
        series = [(r["date"], r["units"][unit]) for r in records if unit in r["units"]]   # newest first
        run = 1
        while run < len(series) and series[run][1] == power:
            run += 1
        changed = run < len(series)                       # the change into this power is in the store
        before = series[run][1] if changed else None
        change_on = series[run - 1][0] if changed else None
        prev = series[1] if len(series) > 1 else (None, None)
        if power >= 100 and change_on != newest["date"]:
            continue
        # The baseline: the unit's day pairs before the change (each pair a report and the one before it).
        pairs = [(series[i + 1][1], series[i][1]) for i in range(run, len(series) - 1)] if changed else []
        n = len(pairs)
        k = sum(1 for a, b in pairs if a >= SHUTDOWN_FROM and b == 0)
        delta = power - before if changed else None
        lower = sum(1 for a, b in pairs if b - a <= delta) if changed else 0
        shutdown = changed and power == 0 and before >= SHUTDOWN_FROM
        rate = k / n if n else None
        anomaly = bool(shutdown and change_on >= hold and n >= BASELINE_MIN and rate <= FLAG_RATE_CAP)
        out.append({"unit": unit, "date": newest["date"], "power": power, "previous_date": prev[0],
                    "previous_power": prev[1], "changed_on": change_on, "power_before": before, "change": delta,
                    "reports_at_power": run, "at_power_since": series[run - 1][0], "baseline_pairs": n, "baseline_shutdowns": k,
                    "baseline_at_or_below": lower, "flag_rate": round(rate, 4) if rate is not None else None,
                    "shutdown": bool(shutdown), "anomaly": anomaly})
    return out


def summary(records: list[dict]) -> dict | None:
    if not records:
        return None
    u = records[0]["units"]
    return {"date": records[0]["date"], "units": len(u), "full": sum(1 for v in u.values() if v >= 100),
            "below": sum(1 for v in u.values() if 0 < v < 100), "zero": sum(1 for v in u.values() if v == 0)}


def reactors_map(records: list[dict]) -> dict:
    """Every unit on the newest report with its power and the one before, for the map layer (site/data/reactors.json)."""
    cat = catalog()["units"]
    if not records:
        return {"date": None, "previous_date": None, "units": []}
    prev = records[1] if len(records) > 1 else {"date": None, "units": {}}
    units = []
    for name, power in sorted(records[0]["units"].items()):
        row = cat.get(name)
        units.append({"name": name, "power": power, "previous": prev["units"].get(name),
                      "plant": row[5] if row else None, "state": row[2] if row else None,
                      "lat": row[0] if row else None, "lon": row[1] if row else None})
    return {"date": records[0]["date"], "previous_date": prev["date"], "units": units}


# ---- placement ---------------------------------------------------------------------------------------------------
@cache
def catalog() -> dict:
    return json.loads((ROOT / "catalog" / "us_reactors.json").read_text(encoding="utf-8"))


def norm(name: str) -> str:
    """A facility name reduced for matching: lower case, Saint for St., without words such as nuclear or station,
    letters and digits only ("St. Lucie" and "Saint Lucie" -> "saintlucie")."""
    s = re.sub(r"\bst\.?(?=\s)", "saint", (name or "").lower())
    return "".join(w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP_WORDS)


@cache
def _index():
    cat = catalog()
    exact, by_base = {}, {}
    for name, row in cat["units"].items():
        exact[norm(name)] = name
        by_base.setdefault(norm(re.sub(r"\s+\d+$", "", name)), []).append(name)
    aliases = {norm(k): norm(v) for k, v in (cat.get("aliases") or {}).items()}
    return exact, by_base, aliases


def place_unit(facility: str, units: list[str], state: str | None):
    """(unit name, catalog row) for a power reactor event's facility and units, or (None, None). The first listed unit
    that the catalog has; else the facility's first unit, when the facility names only one plant. Always in the
    event's state."""
    exact, by_base, aliases = _index()
    cat = catalog()["units"]
    b = norm(facility)
    b = aliases.get(b, b)
    ok = lambda n: n and (not state or cat[n][2] == state)  # noqa: E731
    for u in units or []:
        n = exact.get(f"{b}{u}")
        if ok(n):
            return n, cat[n]
    for n in [exact.get(b)] + sorted(by_base.get(b, []), key=lambda x: (len(x), x)):
        if ok(n):
            return n, cat[n]
    return None, None


@cache
def _counties() -> dict:
    doc = json.loads((ROOT / "catalog" / "us_counties.json").read_text(encoding="utf-8"))
    out = {}
    for fips, (lat, lon, name, st) in doc["counties"].items():
        key = re.sub(r"\s+(county|parish|borough|census area|city and borough|municipality)$", "", name.lower())
        out[(key, st)] = (lat, lon, fips)
    return out


def county_point(county: str | None, state: str | None):
    """(lat, lon, fips) of a county's Census internal point by the name an event gives (SAN LUIS OBISPO), or None."""
    if not county or not state:
        return None
    key = re.sub(r"\s+(county|parish)$", "", " ".join(county.lower().split()))
    return _counties().get((key, state)) or _counties().get((key.replace("saint ", "st. "), state))


def sentence(s: str | None) -> str | None:
    """The NRC's upper-case headline in sentence case, keeping known acronyms and the emergency classes' names:
    "UNUSUAL EVENT - LOSS OF ALL OFFSITE POWER" -> "Unusual Event - loss of all offsite power"."""
    if not s:
        return None
    if not s.isupper():
        return s
    words = s.lower().split()
    out = []
    for w in words:
        core = re.sub(r"[^a-z0-9]", "", w)
        out.append(w.upper() if core in ACRONYMS or re.fullmatch(r"\d+[a-z]{1,2}|[a-z]+\d+[a-z]?", core) else w)
    text = " ".join(out)
    for _, name in CLASSES[1:]:
        text = re.sub(rf"\b{name.lower()}\b", name, text)
    return text[:1].upper() + text[1:]
