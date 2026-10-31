"""Offline tests for Elements (no network; FIRMS_MAP_KEY is set only inside tests, to a dummy value). Run as a plain script or with unittest. Fixtures copy the live formats seen on
31 Oct 2026, including the awkward cases (GDACS's empty body when nothing matches, its cyclone stage label paired with
the event's maximum wind, floods that carry "Magnitude 0", drought names that list every country)."""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, firms, sources  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402

NOW = datetime(2026, 10, 31, 22, 0, tzinfo=timezone.utc)
FETCHED = "2026-10-31T21:56:00Z"


def quake(eid, mag, lon, lat, alert=None, tsunami=0):
    return {"type": "Feature", "id": eid, "geometry": {"type": "Point", "coordinates": [lon, lat, 10.0]},
            "properties": {"mag": mag, "place": "somewhere", "time": 1793481639000, "updated": 1793482556000,
                           "alert": alert, "tsunami": tsunami, "sig": 400,
                           "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{eid}"}}


USGS = {"type": "FeatureCollection", "features": [
    quake("us1", 5.0, 138.25, 36.2),              # inland Honshu: Japan
    quake("us2", 6.1, -150.0, -30.0, "yellow", 1),  # open Pacific: no country
    quake("us3", 6.4, 168.0, -15.5, "green"),
    {"type": "Feature", "id": "us4", "geometry": {"type": "Point", "coordinates": [10, 10, 5]},
     "properties": {"mag": None}},                 # no magnitude: skipped
]}


def gd(etype, eid, name, alert, episode_alert, sev_text, sev_value, unit="", lon=80.0, lat=15.0, current="true"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"eventtype": etype, "eventid": eid, "episodeid": 3, "name": name, "alertlevel": alert,
                           "episodealertlevel": episode_alert, "alertscore": 2, "fromdate": "2026-10-26T00:00:00",
                           "todate": "2026-10-28T06:00:00", "iscurrent": current, "country": "India",
                           "severitydata": {"severity": sev_value, "severitytext": sev_text, "severityunit": unit},
                           "url": {"report": f"https://www.gdacs.org/report.aspx?eventid={eid}&eventtype={etype}"}}}


GDACS_HIGH = {"type": "FeatureCollection", "features": [
    gd("TC", 1001, "Tropical Cyclone ARNAB-26", "Red", "Orange", "Tropical Storm (maximum wind speed of 222 km/h)",
       222.2208, "km/h", 86.0, 17.0),
    gd("DR", 1002, "Drought in Andorra, Albania, Austria, Bosnia  and  Herzegovina, Belgium, Bulgaria, Switzerland, "
       "Czechia, Germany, Denmark", "Orange", "Orange", "Medium impact for agricultural drought in 2009754 km2",
       2009754.0, "km2", 15.0, 48.0),
]}
GDACS_GREEN = {"type": "FeatureCollection", "features": [
    gd("FL", 1003, "Flood in Bhutan", "Green", "Green", "Magnitude 0 ", 0.0, "", 89.8, 27.6),
    gd("TC", 1001, "Tropical Cyclone ARNAB-26", "Red", "Orange", "Tropical Storm (maximum wind speed of 222 km/h)",
       222.2208, "km/h", 86.0, 17.0),     # the same event in both answers: kept once
]}

NHC = {"activeStorms": [{"id": "al182026", "name": "Rafael", "classification": "HU", "intensity": "85", "pressure": "975",
                         "latitudeNumeric": 24.1, "longitudeNumeric": -86.2, "movementDir": 290, "movementSpeed": 9,
                         "lastUpdate": "2026-10-31T21:00:00.000Z",
                         "publicAdvisory": {"url": "https://www.nhc.noaa.gov/text/MIATCPAT3.shtml"}}]}

CEMS = {"results": [
    {"code": "EMSR935", "name": "Flood in Alicante-Valencia Regions, Spain", "category": "Flood",
     "eventTime": "2026-10-19T03:10:00", "activationTime": "2026-10-19T16:03:00", "lastUpdate": "2026-10-28T08:51:30",
     "closed": True, "n_products": 2, "countries": "['Spain']", "centroid": "POINT (0.023 38.816)"},
    {"code": "EMSR936", "name": "Wildfire in Somewhere", "category": "Wildfire", "eventTime": "2026-10-30T10:00:00",
     "activationTime": "2026-10-30T12:00:00", "lastUpdate": None, "closed": False, "n_products": 0,
     "countries": ["Greece"], "centroid": None},
    {"code": "EMSR800", "name": "Old flood", "category": "Flood", "eventTime": "2026-01-10T00:00:00",
     "activationTime": "2026-01-10T06:00:00", "lastUpdate": "2026-02-01T00:00:00", "closed": True, "n_products": 5,
     "countries": "['Italy']", "centroid": "POINT (12.0 43.0)"},
]}


def fake_fetch(answers):
    """answers: list of (body or None, error) returned in order."""
    it = iter(answers)
    return lambda url, timeout=40: next(it)


def dataset():
    gdacs, _ = sources.collect_gdacs([], NOW, fake_fetch([(json.dumps(GDACS_HIGH).encode(), None),
                                                          (json.dumps(GDACS_GREEN).encode(), None)]))
    return {"usgs": {"records": sources.parse_usgs(USGS), "fetched_at": FETCHED},
            "gdacs": {"records": gdacs, "fetched_at": FETCHED},
            "nhc": {"records": sources.parse_nhc(NHC), "fetched_at": FETCHED},
            "cems": {"records": sources.parse_cems(CEMS), "fetched_at": FETCHED}}


class Sources(unittest.TestCase):
    def test_usgs(self):
        q = sources.parse_usgs(USGS)
        self.assertEqual([x["id"] for x in q], ["us1", "us2", "us3"])
        self.assertEqual(q[0]["countries"], ["JP"])
        self.assertEqual(q[1]["countries"], [])
        self.assertEqual(q[0]["time"], "2026-10-31T21:20:39Z")
        self.assertTrue(q[1]["tsunami"])
        self.assertEqual(q[0]["depth_km"], 10.0)

    def test_gdacs_fields(self):
        e = {x["id"]: x for x in sources.parse_gdacs(GDACS_HIGH)}
        tc = e["TC-1001"]
        self.assertEqual((tc["alert"], tc["latest_alert"]), ("red", "orange"))
        self.assertEqual(tc["from"], "2026-10-26T00:00:00Z")
        self.assertTrue(tc["current"])
        self.assertNotIn("  ", e["DR-1002"]["name"])

    def test_gdacs_merge_and_empty(self):
        got, err = sources.collect_gdacs([], NOW, fake_fetch([(json.dumps(GDACS_HIGH).encode(), None),
                                                              (json.dumps(GDACS_GREEN).encode(), None)]))
        self.assertIsNone(err)
        self.assertEqual(sorted(x["id"] for x in got), ["DR-1002", "FL-1003", "TC-1001"])
        # an empty body means nothing matched: no events, no error
        got, err = sources.collect_gdacs(["old"], NOW, fake_fetch([(b"", None), (b"  ", None)]))
        self.assertEqual((got, err), ([], None))
        # both queries failing keeps the last good data and reports why
        got, err = sources.collect_gdacs(["old"], NOW, fake_fetch([(None, "HTTP 503"), (None, "HTTP 503")]))
        self.assertEqual(got, ["old"])
        self.assertIn("HTTP 503", err)

    def test_gdacs_urls(self):
        u = sources.gdacs_urls(NOW)
        self.assertTrue(all("fromdate=2026-10-17&todate=2026-10-31" in x for x in u))
        self.assertIn("alertlevel=Orange;Red", u[0])
        self.assertNotIn("EQ", u[1].split("eventlist=")[1])  # green earthquakes are left to USGS

    def test_nhc(self):
        s = sources.parse_nhc(NHC)[0]
        self.assertEqual((s["name"], s["classification"], s["lat"], s["lon"]), ("Rafael", "HU", 24.1, -86.2))
        self.assertEqual(s["updated"], "2026-10-31T21:00:00Z")

    def test_cems(self):
        a = {x["code"]: x for x in sources.parse_cems(CEMS)}
        self.assertEqual(a["EMSR935"]["countries"], ["ES"])
        self.assertEqual((a["EMSR935"]["lon"], a["EMSR935"]["lat"]), (0.023, 38.816))
        self.assertEqual(a["EMSR936"]["countries"], ["GR"])
        self.assertIsNone(a["EMSR936"]["lon"])
        self.assertTrue(a["EMSR935"]["closed"])
        self.assertFalse(a["EMSR936"]["closed"])

    def test_failing_source_keeps_old(self):
        got, err = sources.collect_usgs(["old"], fake_fetch([(None, "network: timeout")]))
        self.assertEqual((got, err), (["old"], "network: timeout"))
        got, err = sources.collect_nhc(["old"], fake_fetch([(b"not json", None)]))
        self.assertEqual(got, ["old"])
        self.assertTrue(err.startswith("parse"))


class Feed(unittest.TestCase):
    def setUp(self):
        self.fc = feed.build(dataset(), NOW)
        self.by = {f["properties"]["id"]: f for f in self.fc["features"]}

    def test_nothing_dropped_and_contract(self):
        self.assertEqual(self.fc["dropped"], [])
        regs = registers.ids(ROOT / "doctrine")
        for f in self.fc["features"]:
            errs = [m for _, sev, m in contract.check(f, regs) if sev == "error"]
            self.assertEqual(errs, [], f["properties"]["id"])

    def test_tiers(self):
        tier = {k: v["properties"]["tier"] for k, v in self.by.items()}
        self.assertEqual(tier["elements:usgs:us2"], "anomaly")      # PAGER yellow
        self.assertEqual(tier["elements:usgs:us3"], "routine")      # PAGER green
        self.assertEqual(tier["elements:usgs:us1"], "routine")      # no PAGER alert
        self.assertEqual(tier["elements:gdacs:TC-1001"], "anomaly")  # GDACS red
        self.assertEqual(tier["elements:gdacs:FL-1003"], "routine")
        p = self.by["elements:usgs:us2"]["properties"]
        self.assertEqual(p["response_stage"], "pager:yellow")
        self.assertEqual(p["baseline_ref"]["id"], "pager-green")
        self.assertNotIn("response_stage", self.by["elements:usgs:us1"]["properties"])

    def test_gdacs_titles(self):
        tc = self.by["elements:gdacs:TC-1001"]["properties"]
        self.assertEqual(tc["title"], "GDACS red alert: Tropical Cyclone ARNAB-26 (maximum wind 222 km/h)")
        self.assertEqual(tc["measures"]["latest_alert"], "orange")
        self.assertEqual(self.by["elements:gdacs:FL-1003"]["properties"]["title"], "GDACS green alert: Flood in Bhutan")
        dr = self.by["elements:gdacs:DR-1002"]["properties"]["title"]
        self.assertIn("and others", dr)
        self.assertIn("2,009,754 km²", dr)
        self.assertLess(len(dr), 170)

    def test_cems_window_and_visual(self):
        self.assertNotIn("elements:cems:EMSR800", self.by)   # closed and older than 60 days
        self.assertIn("elements:cems:EMSR935", self.by)
        p = self.by["elements:cems:EMSR936"]
        self.assertIsNone(p["geometry"])
        self.assertEqual(p["properties"]["visual"]["url"], "https://rapidmapping.emergency.copernicus.eu/EMSR936/")
        self.assertEqual(p["properties"]["response_stage"], "cems:activated")

    def test_nhc_item(self):
        p = self.by["elements:nhc:al182026"]["properties"]
        self.assertEqual(p["title"], "Hurricane Rafael: 85 kt, 975 mb")

    def test_deterministic(self):
        again = feed.build(dataset(), NOW)
        self.assertEqual(json.dumps(self.fc, sort_keys=True), json.dumps(again, sort_keys=True))
        self.assertEqual(self.fc["generated_at"], FETCHED)


FIRMS_HEAD = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"


def firms_csv(rows, conf_style="word"):
    word = {"n": "nominal", "h": "high", "l": "low"}
    lines = [f"{lat},{lon},330,0.4,0.5,{day},{tm},N20,{word[c] if conf_style == 'word' else c},2.0NRT,290,{frp},D"
             for lat, lon, day, tm, c, frp in rows]
    return (FIRMS_HEAD + "\n".join(lines) + "\n").encode()


BRAZIL = [(-10.2 - i * 0.01, -55.3 - i * 0.01, "2026-10-31", "1530", "h" if i == 0 else "n", 10.0 + i) for i in range(12)]
FIRE_ROWS = BRAZIL + [
    (-10.25, -55.35, "2026-10-31", "1532", "l", 99.0),   # low confidence: dropped
    (-10.2, -55.3, "2026-10-30", "0100", "n", 5.0),      # outside the 24 hours, still counted for 30 Oct
    (23.7, 121.0, "2026-10-31", "45", "n", 3.0),         # Taiwan; acq_time without leading zeros
    (0.0, -30.0, "2026-10-31", "1200", "n", 1.0),        # mid-Atlantic: no country
]
KEY = "0123456789abcdef0123456789abcdef"


def firms_fetch(answers, seen):
    """answers: {'api': body or None, 'public': body or None, 'status': body}; seen collects the URLs asked for."""
    def fetch(url, timeout=40, max_bytes=None):
        seen.append(url)
        kind = "status" if "mapkey_status" in url else "api" if "/api/area/" in url else "public"
        body = answers.get(kind)
        return (body, None) if body is not None else (None, "HTTP 503")
    return fetch


class Firms(unittest.TestCase):
    def test_parse_both_confidence_styles(self):
        for style in ("word", "letter"):
            dets = firms.parse(firms_csv(FIRE_ROWS, style))
            self.assertEqual(len(dets), len(FIRE_ROWS) - 1, style)  # the low one is dropped
            self.assertTrue(dets[0][3])                              # high confidence
        tw = [x for x in firms.parse(firms_csv(FIRE_ROWS)) if x[1] == 23.7][0]
        self.assertEqual(tw[2], datetime(2026, 10, 31, 0, 45, tzinfo=timezone.utc))

    def test_aggregate(self):
        a = firms.aggregate(firms.parse(firms_csv(FIRE_ROWS)), NOW)
        self.assertEqual(a["window"], ["2026-10-30T22:00:00Z", "2026-10-31T22:00:00Z"])
        self.assertEqual(a["detections"], 14)                     # 12 Brazil + Taiwan + Atlantic
        by_cc = {}
        for c in a["cells"]:
            by_cc[c[7]] = by_cc.get(c[7], 0) + c[2]
        self.assertEqual(by_cc, {"BR": 12, "TW": 1, None: 1})
        self.assertEqual(a["daily"]["2026-10-30"], {"BR": 1})
        self.assertEqual(a["daily"]["2026-10-31"], {"BR": 12, "TW": 1})
        br = max(a["cells"], key=lambda c: c[2])
        self.assertEqual((br[3], br[5]), (1, 21.0))               # one high-confidence; largest FRP 21 MW
        self.assertTrue(all(c[0] % 0.5 == 0.25 for c in a["cells"]))  # cell centres

    def test_no_key_reads_public_files(self):
        seen = []
        with patch.dict(os.environ, {"FIRMS_MAP_KEY": ""}):
            p, err = firms.collect_firms(None, NOW, firms_fetch({"public": firms_csv(FIRE_ROWS)}, seen))
        self.assertIsNone(err)
        self.assertEqual(set(p["via"].values()), {"public files"})
        self.assertTrue(all("/data/active_fire/" in u for u in seen))
        self.assertEqual(len(seen), 3)

    def test_key_uses_api_and_never_leaks(self):
        seen = []
        status = json.dumps({"transaction_limit": 5000, "current_transactions": 6, "secret_echo": KEY}).encode()
        with patch.dict(os.environ, {"FIRMS_MAP_KEY": KEY}):
            p, err = firms.collect_firms(None, NOW, firms_fetch({"api": firms_csv(FIRE_ROWS, "letter"), "status": status}, seen))
        self.assertIsNone(err)
        self.assertEqual(set(p["via"].values()), {"api"})
        self.assertTrue(seen[0].endswith(f"/api/area/csv/{KEY}/VIIRS_NOAA20_NRT/world/2"))
        self.assertEqual(p["key_status"], {"transaction_limit": 5000, "current_transactions": 6})
        self.assertNotIn(KEY, json.dumps(p))
        self.assertIn("key used 6 of 5000 transactions", firms.summary(p))

    def test_api_failure_falls_back_without_leaking(self):
        seen = []
        with patch.dict(os.environ, {"FIRMS_MAP_KEY": KEY}):
            p, err = firms.collect_firms(None, NOW, firms_fetch({"api": b"Invalid MAP_KEY " + KEY.encode(),
                                                                 "public": firms_csv(FIRE_ROWS)}, seen))
        self.assertEqual(set(p["via"].values()), {"public files"})
        self.assertIn("answer was not CSV", err)
        self.assertNotIn(KEY, err + json.dumps(p))

    def test_bad_key_is_not_sent(self):
        seen = []
        with patch.dict(os.environ, {"FIRMS_MAP_KEY": "not-a-key/../x"}):
            p, err = firms.collect_firms(None, NOW, firms_fetch({"public": firms_csv(FIRE_ROWS)}, seen))
        self.assertFalse(any("/api/" in u for u in seen))
        self.assertIn("not a 32-character key", err)

    def test_all_fail_keeps_old(self):
        with patch.dict(os.environ, {"FIRMS_MAP_KEY": ""}):
            p, err = firms.collect_firms({"cells": ["old"]}, NOW, firms_fetch({}, []))
        self.assertEqual(p, {"cells": ["old"]})
        self.assertIn("HTTP 503", err)

    def test_history_keeps_complete_days_only(self):
        a = firms.aggregate(firms.parse(firms_csv(FIRE_ROWS)), NOW)
        h = firms.update_history({"days": {"2026-10-29": {"BR": 3}}}, a, "2026-10-31")
        self.assertEqual(list(h["days"]), ["2026-10-29", "2026-10-30"])  # 31 Oct is today: still filling
        self.assertEqual(h["days"]["2026-10-30"], {"BR": 1})

    def test_feed_items(self):
        a = firms.aggregate(firms.parse(firms_csv(FIRE_ROWS)), NOW)
        d = dataset()
        d["firms"] = {"records": a, "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        fire = {f["properties"]["id"]: f["properties"] for f in fc["features"] if f["properties"]["id"].startswith("elements:firms:")}
        self.assertEqual(list(fire), ["elements:firms:BR"])        # Taiwan has 1 detection, under the minimum of 10
        p = fire["elements:firms:BR"]
        self.assertEqual(p["title"], "12 fire and heat detections in Brazil, past 24 hours (VIIRS)")
        self.assertEqual((p["precision_class"], p["tier"], p["countries"]), ("country", "routine", ["BR"]))
        self.assertEqual(p["data_as_of"], "2026-10-31T15:30:00Z")

    def test_country_names_and_taiwan(self):
        from elements.common import country_at, country_name
        self.assertEqual(country_at(23.7, 121.0), "TW")
        self.assertEqual(country_name("TW"), "Taiwan")
        self.assertEqual(country_name("SS"), "South Sudan")
        self.assertEqual(country_name("BR"), "Brazil")


class Registers(unittest.TestCase):
    def test_registers_valid(self):
        self.assertEqual(registers.check(ROOT / "doctrine"), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
