"""Offline tests for Elements' EMSC earthquake and NIFC wildfire lanes. Fixtures copy the live formats of the
seismicportal.eu FDSN event service and the NIFC WFIGS incident service on 4 Nov 2026 (trimmed)."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import emsc, feed, nifc  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402

NOW = datetime(2026, 11, 4, 22, 0, tzinfo=timezone.utc)
FETCHED = "2026-11-04T21:56:00Z"


def ev(unid, mag, lat, lon, time, auth="EMSC", region="SAMAR, PHILIPPINES"):
    return {"type": "Feature", "id": unid, "geometry": {"type": "Point", "coordinates": [lon, lat, -10]},
            "properties": {"source_id": "1", "source_catalog": "EMSC-RTS", "lastupdate": "2026-11-04T18:54:44.5Z",
                           "time": time, "flynn_region": region, "lat": lat, "lon": lon, "depth": 50.0, "evtype": "ke",
                           "auth": auth, "mag": mag, "magtype": "mb", "unid": unid}}


EMSC = {"type": "FeatureCollection", "features": [
    ev("e1", 5.1, 36.0, 141.0, "2026-11-04T10:00:20.0Z", region="NEAR EAST COAST OF HONSHU, JAPAN"),  # matches u1
    ev("e2", 4.8, -20.0, -175.0, "2026-11-03T05:00:05Z", auth="NEIC", region="TONGA"),               # matches u2, USGS's own
    ev("e3", 4.6, 11.31, 125.03, "2026-11-04T16:14:39.4Z"),                                           # EMSC only
    ev("e4", 4.5, 10.0, -79.0, "2026-11-02T00:00:00Z", auth="NEIC", region="PANAMA"),                 # NEIC, unmatched: dropped
    ev("e5", 4.9, 36.5, 141.5, "2026-11-04T10:03:00Z", region="OFF EAST COAST OF HONSHU, JAPAN"),     # 160 s from u1: no match
]}
USGS = [  # records as elements.sources.parse_usgs writes them
    {"id": "u1", "mag": 5.2, "place": "70 km E of Hasaki, Japan", "time": "2026-11-04T10:00:00Z", "alert": None, "tsunami": False,
     "sig": 400, "url": "https://earthquake.usgs.gov/earthquakes/eventpage/u1", "depth_km": 30.0, "lon": 141.2, "lat": 36.1,
     "countries": []},
    {"id": "u2", "mag": 4.9, "place": "Tonga", "time": "2026-11-03T05:00:00Z", "alert": None, "tsunami": False, "sig": 380,
     "url": "https://earthquake.usgs.gov/earthquakes/eventpage/u2", "depth_km": 10.0, "lon": -175.1, "lat": -20.1, "countries": []},
    {"id": "u3", "mag": 4.7, "place": "Kermadec Islands", "time": "2026-11-01T00:00:00Z", "alert": None, "tsunami": False, "sig": 340,
     "url": "https://earthquake.usgs.gov/earthquakes/eventpage/u3", "depth_km": 10.0, "lon": -177.0, "lat": -30.0, "countries": []},
]


def wf(name, acres, pct, found_ms, typ="WF", out=None, state="US-OR", county="Wasco", irwin="{ABC-1}", lon=-121.5, lat=45.25):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"IncidentName": name, "IncidentSize": acres, "PercentContained": pct, "FireDiscoveryDateTime": found_ms,
                           "ModifiedOnDateTime_dt": 1793582962000, "POOState": state, "POOCounty": county,
                           "IncidentTypeCategory": typ, "IrwinID": irwin, "UniqueFireIdentifier": "2026-ORPRD-1",
                           "FireCause": "Human", "IncidentComplexityLevel": "Type 3 Incident", "FireOutDateTime": out}}


JUNE, LAST_WEEK = 1782734686000, 1793000000000      # 29 Jun 2026; 26 Oct 2026
NIFC = {"type": "FeatureCollection", "features": [
    wf("GRASSHOPPER", 93972, 98, JUNE, irwin="{G-1}"),                         # uncontained, old: kept
    wf("Ranger Road", 283283, 100, JUNE, irwin="{R-1}"),                       # contained and old: dropped
    wf("New Ridge", 1500, 100, LAST_WEEK, irwin="{N-1}"),                      # contained but new: kept
    wf("Cedar Complex", 450, None, LAST_WEEK, irwin="{C-1}", state="US-CA", county="Shasta"),
    wf("Pile Burn", 40, 0, LAST_WEEK, typ="RX", irwin="{P-1}"),                 # prescribed: dropped
    wf("Out Fire", 900, 50, LAST_WEEK, out=1793300000000, irwin="{O-1}"),      # declared out: dropped
    wf("Small", 12, 10, LAST_WEEK, irwin="{S-1}"),                             # kept, but under 100 acres: no feed item
]}


def base_data():
    return {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}


class Emsc(unittest.TestCase):
    def test_parse(self):
        e = emsc.parse(EMSC)
        self.assertEqual(len(e), 5)
        self.assertEqual(e[2]["region"], "Samar, Philippines")
        self.assertEqual(e[2]["time"], "2026-11-04T16:14:39Z")
        self.assertEqual(e[2]["url"], "https://www.seismicportal.eu/eventdetails.html?unid=e3")
        self.assertEqual(e[2]["countries"], [])               # just off Samar's coast: at sea, no country
        self.assertEqual(emsc.parse({"features": [ev("x", 4.6, 7.5, 125.0, "2026-11-04T00:00:00Z")]})[0]["countries"], ["PH"])

    def test_collect(self):
        ok = lambda url, timeout=40: (json.dumps(EMSC).encode(), None)   # noqa: E731
        self.assertEqual(len(emsc.collect([], NOW, ok)[0]), 5)
        self.assertEqual(emsc.collect(["old"], NOW, lambda url, timeout=40: (b"", None)), ([], None))
        self.assertEqual(emsc.collect(["old"], NOW, lambda url, timeout=40: (None, "HTTP 503")), (["old"], "HTTP 503"))
        self.assertIn("starttime=2026-10-28T22:00:00", emsc.url(NOW))

    def test_match(self):
        m = emsc.match(USGS, emsc.parse(EMSC))
        self.assertEqual({k: v["id"] for k, v in m.items()}, {"u1": "e1", "u2": "e2"})

    def test_feed(self):
        d = base_data()
        d["usgs"] = {"records": USGS, "fetched_at": FETCHED}
        d["emsc"] = {"records": emsc.parse(EMSC), "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        regs = registers.ids(ROOT / "doctrine")
        for f in fc["features"]:
            self.assertEqual([m for _, sev, m in contract.check(f, regs) if sev == "error"], [], f["properties"]["id"])
        by = {f["properties"]["id"]: f["properties"] for f in fc["features"]}
        u1, u2, u3 = by["elements:usgs:u1"], by["elements:usgs:u2"], by["elements:usgs:u3"]
        self.assertEqual([s["id"] for s in u1["sources"]], ["usgs-earthquakes", "emsc"])     # independent corroboration
        self.assertEqual((u1["measures"]["emsc"]["magnitude"], u1["measures"]["emsc"]["independent"]), (5.1, True))
        self.assertEqual([s["id"] for s in u2["sources"]], ["usgs-earthquakes"])              # EMSC carried NEIC's solution
        self.assertFalse(u2["measures"]["emsc"]["independent"])
        self.assertNotIn("emsc", u3["measures"])
        only = sorted(k for k in by if k.startswith("elements:emsc:"))
        self.assertEqual(only, ["elements:emsc:e3", "elements:emsc:e5"])                      # e4 is NEIC: dropped
        self.assertEqual(by["elements:emsc:e3"]["title"], "M4.6 earthquake, Samar, Philippines (EMSC)")


class Nifc(unittest.TestCase):
    def test_parse_filters(self):
        w = nifc.parse(NIFC, NOW)
        self.assertEqual([x["name"] for x in w], ["Grasshopper", "New Ridge", "Cedar Complex", "Small"])
        g = w[0]
        self.assertEqual((g["state"], g["county"], g["contained"], g["discovered"]), ("OR", "Wasco", 98, "2026-06-29T12:04:46Z"))
        self.assertEqual(g["id"], "{G-1}")

    def test_collect(self):
        ok = lambda url, timeout=40: (json.dumps(NIFC).encode(), None)   # noqa: E731
        self.assertEqual(len(nifc.collect([], NOW, ok)[0]), 4)
        err = lambda url, timeout=40: (json.dumps({"error": {"code": 500, "message": "x"}}).encode(), None)   # noqa: E731
        self.assertEqual(nifc.collect(["old"], NOW, err), (["old"], "service error 500"))
        self.assertIn("IncidentTypeCategory%3D%27WF%27", nifc.URL)

    def test_feed(self):
        d = base_data()
        d["nifc"] = {"records": nifc.parse(NIFC, NOW), "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        t = {f["properties"]["id"]: f["properties"]["title"] for f in fc["features"]}
        self.assertEqual(t, {
            "elements:nifc:g-1": "Grasshopper Fire, Wasco County, OR: 93,972 acres, 98% contained (NIFC)",
            "elements:nifc:n-1": "New Ridge Fire, Wasco County, OR: 1,500 acres, 100% contained (NIFC)",
            "elements:nifc:c-1": "Cedar Complex, Shasta County, CA: 450 acres, containment not reported (NIFC)"})


if __name__ == "__main__":
    unittest.main(verbosity=1)
