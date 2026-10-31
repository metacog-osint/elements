"""Shared helpers: fetching, time, JSON files and source health. Standard library only."""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))  # the doctrine kit
from tic_doctrine import geo  # noqa: E402

USER_AGENT = "Elements/0.1 (The Intelligence Company; https://github.com/metacog-osint/elements)"
MAX_BYTES = 8 * 1024 * 1024


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc(value: str) -> str | None:
    """An ISO 8601 time with any offset, as UTC ending in Z."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, timeout: int = 40, max_bytes: int = MAX_BYTES) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError(f"response over {max_bytes} bytes")
    return body


def fetch_or_none(url: str, timeout: int = 40, max_bytes: int = MAX_BYTES):
    """(body, None) or (None, short error): a failing source never stops the run."""
    try:
        return fetch(url, timeout, max_bytes), None
    except Exception as e:  # noqa: BLE001 - every failure is reported, none is fatal
        return None, describe(e)


def describe(e: Exception) -> str:
    """An error without the URL (none of ours carry secrets, but keep logs short)."""
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}"
    if isinstance(e, urllib.error.URLError):
        return f"network: {type(e.reason).__name__}"
    return type(e).__name__ + (f": {e}" if str(e) else "")


def load(name: str, default=None):
    p = DATA / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(name: str, obj) -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                             encoding="utf-8", newline="\n")


# The kit's country file (Natural Earth) codes Taiwan "CN-TW" and abbreviates some names ("S. Sudan"). Until the kit
# fixes both, Elements normalises them here.
_NE_CODE = {"TW": "CN-TW"}
_FULL_NAMES = {
    "TW": "Taiwan", "SS": "South Sudan", "CD": "Democratic Republic of the Congo", "CF": "Central African Republic",
    "GQ": "Equatorial Guinea", "DO": "Dominican Republic", "BA": "Bosnia and Herzegovina", "EH": "Western Sahara",
    "SB": "Solomon Islands", "MH": "Marshall Islands", "MP": "Northern Mariana Islands", "VI": "US Virgin Islands",
    "GS": "South Georgia and the South Sandwich Islands", "IO": "British Indian Ocean Territory", "PN": "Pitcairn Islands",
    "FK": "Falkland Islands", "KY": "Cayman Islands", "VG": "British Virgin Islands", "TC": "Turks and Caicos Islands",
    "VC": "Saint Vincent and the Grenadines", "KN": "Saint Kitts and Nevis", "CK": "Cook Islands",
    "PM": "Saint Pierre and Miquelon", "WF": "Wallis and Futuna", "PF": "French Polynesia",
    "TF": "French Southern and Antarctic Lands", "FO": "Faroe Islands", "HM": "Heard Island and McDonald Islands",
    "AG": "Antigua and Barbuda", "AU": "Australia"}


def iso(cc: str | None) -> str | None:
    """A kit country code as ISO 3166-1 alpha-2."""
    return {v: k for k, v in _NE_CODE.items()}.get(cc, cc) if cc else None


def country_at(lat: float, lon: float) -> str | None:
    return iso(geo.country_at(lat, lon))


def country_name(cc: str) -> str:
    return _FULL_NAMES.get(cc) or geo.name(_NE_CODE.get(cc, cc)) or cc


def country_point(cc: str):
    """[lat, lon] label point, or None."""
    return geo.point(cc) or geo.point(_NE_CODE.get(cc, cc))


def health(source: str, ok: bool, detail: str = "", when: str | None = None) -> None:
    """Record a source's latest attempt in data/health.json: last_ok, last_error, consecutive failures."""
    when = when or now_utc()
    h = load("health.json", {})
    s = h.setdefault(source, {"last_ok": None, "last_error": None, "failures": 0})
    s["checked_at"] = when
    if ok:
        s.update({"last_ok": when, "failures": 0, "detail": detail})
    else:
        s.update({"last_error": when, "failures": s.get("failures", 0) + 1, "detail": detail})
    save("health.json", h)
