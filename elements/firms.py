"""NASA FIRMS fire and thermal-anomaly detections from VIIRS on NOAA-20, NOAA-21 and Suomi-NPP, past 24 hours,
gathered into half-degree cells.

With FIRMS_MAP_KEY set, Elements asks the FIRMS area API, which adds real-time and ultra-real-time detections to the
near-real-time ones. Without a key, or when the API fails for a satellite, it reads FIRMS's public files for that
satellite (near-real-time only, about three hours behind). The key goes only into the request: errors never carry the
URL, and nothing FIRMS sends back is echoed.

Detections are not fires. A fire is seen again on each overpass, and FIRMS's near-real-time data does not separate
fires from gas flares, volcanoes and industrial heat sources. Low-confidence detections are dropped."""
import csv
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone

from .common import country_at, fetch_or_none

API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/world/2"
STATUS = "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={key}"
PUBLIC = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/{path}"
SENSORS = {"VIIRS_NOAA20_NRT": "noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv",
           "VIIRS_NOAA21_NRT": "noaa-21-viirs-c2/csv/J2_VIIRS_C2_Global_24h.csv",
           "VIIRS_SNPP_NRT": "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv"}
CELL = 0.5                     # degrees
MAX_BYTES = 48 * 1024 * 1024   # one satellite's two days is about 8 MB
KEEP_DAYS = 400
KEY_RE = re.compile(r"^[0-9a-z]{32}$")


def map_key():
    """(key, problem): the key when it looks like a FIRMS MAP_KEY (32 lower-case letters and digits)."""
    k = (os.environ.get("FIRMS_MAP_KEY") or "").strip()
    if not k:
        return None, None
    return (k, None) if KEY_RE.match(k) else (None, "FIRMS_MAP_KEY is set but is not a 32-character key")


def parse(body: bytes) -> list[tuple]:
    """FIRMS VIIRS CSV to (lon, lat, time, high, frp) for nominal and high confidence. The API writes confidence as
    l/n/h, the public files as low/nominal/high."""
    out = []
    for r in csv.DictReader(io.StringIO(body.decode("utf-8", "replace"))):
        conf = (r.get("confidence") or "").strip().lower()[:1]
        if conf not in ("n", "h"):
            continue
        try:
            t = datetime.strptime(r["acq_date"] + (r.get("acq_time") or "").strip().zfill(4), "%Y-%m-%d%H%M")
            out.append((float(r["longitude"]), float(r["latitude"]), t.replace(tzinfo=timezone.utc), conf == "h",
                        float(r.get("frp") or 0)))
        except (KeyError, ValueError):
            continue
    return out


def _is_csv(body) -> bool:
    return bool(body) and body.lstrip()[:9].lower() == b"latitude,"


def key_status(body: bytes) -> dict:
    """The transaction counts from FIRMS's key-status answer, and nothing else."""
    try:
        d = json.loads(body)
    except ValueError:
        return {}
    if not isinstance(d, dict):
        return {}
    return {k: v for k, v in d.items() if "transaction" in k.lower() and isinstance(v, (int, float, str)) and len(str(v)) < 40}


def aggregate(dets: list[tuple], now: datetime) -> dict:
    """Half-degree cells for the past 24 hours, and per-country counts for each UTC day in the data."""
    start = now - timedelta(hours=24)
    cells = {}
    for lon, lat, t, high, frp in dets:
        key = (int((lon + 180) // CELL), int((lat + 90) // CELL))
        c = cells.get(key)
        if c is None:
            c = cells[key] = {"n": 0, "high": 0, "frp": 0.0, "max": 0.0, "latest": None, "sx": 0.0, "sy": 0.0, "m": 0,
                              "days": {}}
        c["m"] += 1
        c["sx"] += lon
        c["sy"] += lat
        day = t.strftime("%Y-%m-%d")
        c["days"][day] = c["days"].get(day, 0) + 1
        if start <= t <= now:
            c["n"] += 1
            c["high"] += high
            c["frp"] += frp
            c["max"] = max(c["max"], frp)
            c["latest"] = max(c["latest"] or t, t)
    rows, daily, total, newest = [], {}, 0, None
    for (ix, iy), c in sorted(cells.items()):
        cc = country_at(c["sy"] / c["m"], c["sx"] / c["m"])  # the country at the cell's centre of detections
        for day, n in c["days"].items():
            if cc:
                daily.setdefault(day, {})
                daily[day][cc] = daily[day].get(cc, 0) + n
        if not c["n"]:
            continue
        total += c["n"]
        newest = max(newest or c["latest"], c["latest"])
        rows.append([round(ix * CELL - 180 + CELL / 2, 2), round(iy * CELL - 90 + CELL / 2, 2), c["n"], c["high"],
                     round(c["frp"], 1), round(c["max"], 1), c["latest"].strftime("%Y-%m-%dT%H:%MZ"), cc])
    return {"window": [start.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ")], "detections": total,
            "newest": newest.strftime("%Y-%m-%dT%H:%MZ") if newest else None, "cell_deg": CELL,
            "columns": ["lon", "lat", "detections", "high_confidence", "frp_sum_mw", "frp_max_mw", "latest", "country"],
            "cells": rows, "daily": {k: dict(sorted(v.items())) for k, v in sorted(daily.items())}}


def collect_firms(old, now: datetime | None = None, fetch=fetch_or_none):
    """(payload, problem). A satellite the API fails for is read from the public files instead; the run fails only
    when no satellite answers, and then keeps the last good payload."""
    now = now or datetime.now(timezone.utc)
    key, problem = map_key()
    notes = [problem] if problem else []
    via, dets = {}, []
    for sensor, path in SENSORS.items():
        body = None
        if key:
            body, err = fetch(API.format(key=key, sensor=sensor), 120, MAX_BYTES)
            if body is not None and not _is_csv(body):
                body, err = None, f"answer was not CSV ({len(body)} bytes)"
            if body is None:
                notes.append(f"{sensor} API: {err}")
            else:
                via[sensor] = "api"
        if body is None:
            body, err = fetch(PUBLIC.format(path=path), 120, MAX_BYTES)
            if body is not None and not _is_csv(body):
                body, err = None, f"answer was not CSV ({len(body)} bytes)"
            if body is None:
                notes.append(f"{sensor} public file: {err}")
                continue
            via[sensor] = "public files"
        dets += parse(body)
    if not via:
        return old or {}, "; ".join(notes) or "no satellite answered"
    payload = aggregate(dets, now)
    payload["via"] = via
    if "api" in via.values():
        body, _ = fetch(STATUS.format(key=key), 30, 64 * 1024)
        if body is not None:
            payload["key_status"] = key_status(body)
    return payload, ("; ".join(notes) or None)


def update_history(history: dict, payload: dict, today: str) -> dict:
    """data/firms_daily.json: detections per country for each complete UTC day (today is still filling, so it is
    left out). A day is rewritten on every run while it is in FIRMS's two-day window, so late detections count."""
    days = dict((history or {}).get("days") or {})
    for day, counts in (payload.get("daily") or {}).items():
        if day < today:
            days[day] = counts
    keep = sorted(days)[-KEEP_DAYS:]
    return {"note": "VIIRS nominal and high-confidence detections (NOAA-20, NOAA-21, Suomi-NPP) per country per UTC day, "
                    "counted to the country at each half-degree cell's centre of detections.",
            "days": {d: days[d] for d in keep}}


def summary(payload: dict) -> str:
    if not payload or not payload.get("cells"):
        return "no detections"
    via = sorted(set((payload.get("via") or {}).values()))
    st = payload.get("key_status") or {}
    used = next((v for k, v in st.items() if "current" in k.lower()), None)
    limit = next((v for k, v in st.items() if "limit" in k.lower()), None)
    return (f"{payload['detections']:,} detections in {len(payload['cells']):,} cells via {' and '.join(via)}"
            + (f"; key used {used} of {limit} transactions" if used is not None and limit is not None else ""))
