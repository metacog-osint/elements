"""Offline tests for Elements. Run as a plain script or with unittest. Fixtures copy the live formats seen on
31 Oct 2026, including the awkward cases (GDACS's empty body when nothing matches, its cyclone stage label paired with
the event's maximum wind, floods that carry "Magnitude 0", drought names that list every country)."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, sources  # noqa: E402
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


class Registers(unittest.TestCase):
    def test_registers_valid(self):
        self.assertEqual(registers.check(ROOT / "doctrine"), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
