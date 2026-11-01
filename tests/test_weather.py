"""Offline tests for Elements' US weather lane (NWS alerts, SPC Day 1 outlook). Fixtures copy the live formats of
api.weather.gov and spc.noaa.gov on 31 Oct 2026 (trimmed)."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, weather  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402

NOW = datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc)
FETCHED = "2026-11-01T01:56:00Z"
POLY = {"type": "Polygon", "coordinates": [[[-159.7, 22.0], [-159.3, 22.0], [-159.3, 22.2], [-159.7, 22.2], [-159.7, 22.0]]]}


def alert(event, severity, area, same, vtec=None, geometry=None, sent="2026-10-31T16:24:00-10:00", ends="2026-10-31T17:45:00-10:00", aid="a1"):
    return {"type": "Feature", "geometry": geometry,
            "properties": {"@id": f"https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.{aid}", "id": f"urn:oid:2.49.0.1.840.0.{aid}",
                           "event": event, "severity": severity, "urgency": "Expected", "certainty": "Likely",
                           "senderName": "NWS Honolulu HI", "areaDesc": area, "sent": sent, "onset": sent, "ends": ends,
                           "expires": ends, "messageType": "Alert", "geocode": {"SAME": same, "UGC": ["XXZ001"]},
                           "parameters": {"VTEC": [vtec]} if vtec else {}}}


NWS = {"type": "FeatureCollection", "features": [
    alert("Flash Flood Warning", "Severe", "Kauai, HI", ["015007"], "/O.CON.PHFO.FF.W.0058.000000T0000Z-261101T0345Z/", POLY, aid="ff"),
    # one Flood Watch in two segments with different actions: one event
    alert("Flood Watch", "Severe", "Northwest Plateau; Hualapai Mountains", ["004015"], "/O.CON.KVEF.FA.A.0007.000000T0000Z-261102T1200Z/", aid="w1",
          sent="2026-10-31T13:00:00-07:00", ends="2026-11-02T05:00:00-07:00"),
    alert("Flood Watch", "Severe", "Lake Havasu and Fort Mohave", ["004015", "032003"], "/O.EXT.KVEF.FA.A.0007.000000T0000Z-261102T1200Z/", aid="w2",
          sent="2026-10-31T14:00:00-07:00", ends="2026-11-02T05:00:00-07:00"),
    alert("Storm Warning", "Severe", "Kiska to Attu Pacific Side", ["058178"], "/O.NEW.PAFC.SR.W.7189.000000T0000Z-261102T1300Z/", aid="sr"),
    alert("Tornado Warning", "Extreme", "San Juan, PR", ["072127"], "/O.NEW.TJSJ.TO.W.0001.000000T0000Z-261101T0300Z/", aid="to"),
    alert("Small Craft Advisory", "Minor", "Coastal waters", [], "/O.NEW.KJAX.SC.Y.0100.000000T0000Z-261101T0300Z/", aid="sc"),
]}

SPC = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[-100.12345, 35.0], [-95.0, 35.0], [-95.0, 38.0], [-100.12345, 35.0]]]]},
     "properties": {"DN": 2, "VALID": "202611011200", "EXPIRE": "202611021200", "ISSUE": "202611010600", "LABEL": "TSTM",
                    "LABEL2": "General Thunderstorms Risk", "stroke": "#55BB55", "fill": "#C1E9C1"}},
    {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[-99.0, 35.5], [-96.0, 35.5], [-96.0, 37.0], [-99.0, 35.5]]]]},
     "properties": {"DN": 4, "VALID": "202611011200", "EXPIRE": "202611021200", "ISSUE": "202611010600", "LABEL": "SLGT",
                    "LABEL2": "Slight Risk", "stroke": "#DDAA00", "fill": "#FFE066"}},
    {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[-98.0, 36.0], [-97.0, 36.0], [-97.0, 36.5], [-98.0, 36.0]]]]},
     "properties": {"DN": 7, "VALID": "202611011200", "EXPIRE": "202611021200", "ISSUE": "202611010600", "LABEL": "MDT",
                    "LABEL2": "Moderate Risk", "stroke": "#CC0000", "fill": "#E06666"}},
]}


class Parse(unittest.TestCase):
    def setUp(self):
        self.n = {e["id"]: e for e in weather.parse_nws(NWS)}

    def test_keeps_severe_and_extreme_and_merges_segments(self):
        self.assertEqual(sorted(self.n), ["KVEF.FA.A.0007.2026", "PAFC.SR.W.7189.2026", "PHFO.FF.W.0058.2026", "TJSJ.TO.W.0001.2026"])
        w = self.n["KVEF.FA.A.0007.2026"]
        self.assertEqual(w["areas"], ["Northwest Plateau", "Hualapai Mountains", "Lake Havasu and Fort Mohave"])
        self.assertEqual(w["counties"], ["04015", "32003"])
        self.assertEqual(w["sent"], "2026-10-31T21:00:00Z")   # the later message
        self.assertEqual(len(w["points"]), 2)                 # Mohave County AZ, Clark County NV

    def test_places(self):
        ff = self.n["PHFO.FF.W.0058.2026"]
        self.assertEqual(ff["geometry"]["type"], "Polygon")
        self.assertEqual(ff["ends"], "2026-11-01T03:45:00Z")
        self.assertEqual(self.n["TJSJ.TO.W.0001.2026"]["countries"], ["PR"])
        sr = self.n["PAFC.SR.W.7189.2026"]                    # a marine zone: no county point, no polygon
        self.assertEqual((sr["points"], sr["geometry"], sr["lat"]), ([], None, None))

    def test_spc(self):
        s = weather.parse_spc(SPC)
        self.assertEqual([(r["label"], r["level"]) for r in s], [("SLGT", 2), ("MDT", 4)])   # general thunder left out
        self.assertEqual(s[0]["expires"], "2026-11-02T12:00:00Z")

    def test_collect_failures_keep_old(self):
        bad = lambda url, timeout=40: (None, "HTTP 503")   # noqa: E731
        self.assertEqual(weather.collect_nws(["old"], bad), (["old"], "HTTP 503"))
        junk = lambda url, timeout=40: (b"not json", None)  # noqa: E731
        got, err = weather.collect_spc(["old"], junk)
        self.assertEqual(got, ["old"])
        self.assertTrue(err.startswith("parse"))


class Feed(unittest.TestCase):
    def test_items(self):
        d = {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}
        d["nws"] = {"records": weather.parse_nws(NWS), "fetched_at": FETCHED}
        d["spc"] = {"records": weather.parse_spc(SPC), "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        regs = registers.ids(ROOT / "doctrine")
        for f in fc["features"]:
            self.assertEqual([m for _, sev, m in contract.check(f, regs) if sev == "error"], [], f["properties"]["id"])
        by = {f["properties"]["id"]: f for f in fc["features"]}
        to = by["elements:nws:TJSJ.TO.W.0001.2026"]["properties"]
        self.assertEqual((to["tier"], to["baseline_ref"]["id"]), ("anomaly", "cap-severity"))
        self.assertEqual(to["title"], "Tornado Warning for San Juan, PR (NWS Honolulu HI)")
        w = by["elements:nws:KVEF.FA.A.0007.2026"]
        self.assertEqual((w["geometry"]["type"], w["properties"]["precision_class"], w["properties"]["tier"]),
                         ("MultiPoint", "approximate", "routine"))
        sr = by["elements:nws:PAFC.SR.W.7189.2026"]
        self.assertIsNone(sr["geometry"])
        self.assertEqual(sr["properties"]["precision_class"], "none")
        self.assertEqual(by["elements:spc:day1:mdt"]["properties"]["tier"], "anomaly")
        self.assertEqual(by["elements:spc:day1:slgt"]["properties"]["title"], "SPC Day 1 convective outlook: Slight Risk (level 2 of 5)")
        self.assertEqual(by["elements:spc:day1:slgt"]["geometry"]["coordinates"][0][0][0], [-99.0, 35.5])

    def test_long_area_lists_are_cut(self):
        self.assertEqual(feed._area_text(["A"] * 3), "A; A; A")
        long = feed._area_text([f"Zone number {i}" for i in range(20)])
        self.assertTrue(long.endswith("more areas") and len(long) <= 90, long)


if __name__ == "__main__":
    unittest.main(verbosity=1)
