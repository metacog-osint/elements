"""Offline tests for Elements' tsunami and drought lanes. Fixtures copy the live formats of tsunami.gov (Atom and
CAP) and the US Drought Monitor's statistics service and map on 31 Oct 2026 (trimmed)."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import drought, feed, tsunami  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
FETCHED = "2026-10-26T11:56:00Z"


def atom(cap_url):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Tsunami Information Statement Number 1</title>
<updated>2026-10-25T02:26:53Z</updated>
<entry><title>in the Bonin Islands, Japan region</title><updated>2026-10-25T02:26:53Z</updated>
<link rel="alternate" href="{cap_url}" type="application/cap+xml"/>
<link rel="related" href="https://www.tsunami.gov/events/PAAQ/2026/10/25/x/1/WEAK53/WEAK53.txt"/></entry></feed>""".encode()


def cap(event, severity, sent, origin, place="in the Bonin Islands, Japan region", mag="7.0", latlon="28.000,139.900 0.000"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><sent>{sent}</sent><status>Actual</status><msgType>Alert</msgType>
<info><event>{event}</event><urgency>Unknown</urgency><severity>{severity}</severity><certainty>Unlikely</certainty>
<headline>This is a {event} Statement   for Alaska.</headline>
<parameter><valueName>EventLocationName</valueName><value>{place}</value></parameter>
<parameter><valueName>EventPreliminaryMagnitude</valueName><value>{mag}</value></parameter>
<parameter><valueName>EventPreliminaryMagnitudeType</valueName><value>Mwp</value></parameter>
<parameter><valueName>EventOriginTime</valueName><value>{origin}</value></parameter>
<parameter><valueName>EventDepth</valueName><value>473 kilometers</value></parameter>
<parameter><valueName>EventLatLon</valueName><value>{latlon}</value></parameter>
</info></alert>""".encode()


NTWC_CAP = "https://www.tsunami.gov/events/PAAQ/2026/10/25/x/1/WEAK53/PAAQCAP.xml"
PTWC_CAP = "https://www.tsunami.gov/events/PHEB/2026/10/24/y/1/WEGM42/PHEBCAP.xml"


def tsunami_fetch(answers, seen=None):
    def fetch(url, timeout=40, max_bytes=None):
        if seen is not None:
            seen.append(url)
        body = answers.get(url)
        return (body, None) if body is not None else (None, "HTTP 503")
    return fetch


LIVE = {tsunami.CENTRES["NTWC"]: atom(NTWC_CAP), tsunami.CENTRES["PTWC"]: atom(PTWC_CAP),
        NTWC_CAP: cap("Tsunami Information", "Minor", "2026-10-25T02:26:53-00:00", "2026-10-25T02:09:24-00:00"),
        # PTWC's live message gave the origin a day early (local date, UTC time)
        PTWC_CAP: cap("Tsunami Information", "Minor", "2026-10-25T02:27:01-00:00", "2026-10-24T02:09:00-00:00",
                      place="BONIN ISLANDS  JAPAN REGION")}


class Tsunami(unittest.TestCase):
    def test_levels(self):
        self.assertEqual([tsunami.level_of(e) for e in ("Tsunami Warning", "Tsunami Advisory", "Tsunami Watch",
                                                        "Tsunami Threat", "Tsunami Information", "")],
                         ["warning", "advisory", "watch", "threat", "information", "information"])

    def test_collect_and_parse(self):
        recs, err = tsunami.collect([], NOW, tsunami_fetch(LIVE))
        self.assertIsNone(err)
        by = {r["centre"]: r for r in recs}
        n = by["NTWC"]
        self.assertEqual((n["level"], n["magnitude"], n["depth_km"], n["origin"]), ("information", 7.0, 473.0, "2026-10-25T02:09:24Z"))
        self.assertEqual((n["lat"], n["lon"]), (28.0, 139.9))
        self.assertEqual(n["headline"], "This is a Tsunami Information Statement for Alaska.")
        self.assertEqual(n["id"], "NTWC-20261025T020924Z")

    def test_later_message_replaces_and_old_ones_age_out(self):
        recs, _ = tsunami.collect([], NOW, tsunami_fetch(LIVE))
        newer = dict(LIVE)
        newer[NTWC_CAP] = cap("Tsunami Advisory", "Moderate", "2026-10-25T03:00:00-00:00", "2026-10-25T02:09:24-00:00")
        recs2, _ = tsunami.collect(recs, NOW, tsunami_fetch(newer))
        self.assertEqual({r["centre"]: r["level"] for r in recs2}, {"NTWC": "advisory", "PTWC": "information"})
        later = datetime(2026, 12, 1, tzinfo=timezone.utc)                # 30 days on: kept no longer
        recs3, err = tsunami.collect(recs2, later, tsunami_fetch({}))
        self.assertEqual(recs3, [])
        self.assertIn("HTTP 503", err)

    def test_feed_items(self):
        recs, _ = tsunami.collect([], NOW, tsunami_fetch(LIVE))
        d = {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}
        d["tsunami"] = {"records": recs, "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        by = {f["properties"]["id"]: f["properties"] for f in fc["features"]}
        n = by["elements:tsunami:NTWC-20261025T020924Z"]
        self.assertEqual(n["title"], "Tsunami information statement (NTWC): preliminary M7.0 in the Bonin Islands, Japan region")
        self.assertEqual((n["tier"], n["data_as_of"], n["measures"]["origin_note"]), ("routine", "2026-10-25T02:26:53Z", None))
        p = by["elements:tsunami:PTWC-20261024T020900Z"]
        self.assertEqual(p["title"], "Tsunami information statement (PTWC): preliminary M7.0 Bonin Islands Japan Region")
        self.assertIn("24 hours before", p["measures"]["origin_note"])
        # a week later the messages leave the feed
        fc2 = feed.build(d, datetime(2026, 11, 2, tzinfo=timezone.utc))
        self.assertFalse([f for f in fc2["features"] if ":tsunami:" in f["properties"]["id"]])

    def test_warning_is_an_anomaly(self):
        live = dict(LIVE)
        live[NTWC_CAP] = cap("Tsunami Warning", "Extreme", "2026-10-25T02:26:53-00:00", "2026-10-25T02:09:24-00:00",
                             latlon="56.0,-155.0 0.000")
        recs, _ = tsunami.collect([], NOW, tsunami_fetch(live))
        d = {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}
        d["tsunami"] = {"records": recs, "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        p = [f["properties"] for f in fc["features"] if f["properties"]["id"].startswith("elements:tsunami:NTWC")][0]
        self.assertEqual((p["tier"], p["baseline_ref"]["id"]), ("anomaly", "tsunami-message-levels"))


STATS = (b"MapDate,AreaOfInterest,None,D0,D1,D2,D3,D4,ValidStart,ValidEnd,StatisticFormatID\r\n"
         b"20261027,Total,39.01,60.99,41.39,22.36,7.83,1.38,2026-10-27,2026-11-02,1\r\n"
         b"20261020,Total,38.58,61.42,42.50,23.98,7.84,1.00,2026-10-20,2026-10-26,1\r\n")
SQUARE = [[-100.01, 35.0], [-98.0, 35.0], [-98.0, 37.0], [-100.01, 37.0], [-100.01, 35.0]]
SPECK = [[-90.0, 30.0], [-89.99, 30.0], [-89.99, 30.01], [-90.0, 30.0]]
MAP = json.dumps({"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"DM": 2}, "geometry": {"type": "MultiPolygon", "coordinates": [[SQUARE], [SPECK]]}},
    {"type": "Feature", "properties": {"DM": 0}, "geometry": {"type": "Polygon", "coordinates": [SQUARE]}}]}).encode()


def drought_fetch(stats, mapbody, seen):
    def fetch(url, timeout=40, max_bytes=None):
        seen.append(url)
        body = stats if "usdmdataservices" in url else mapbody
        return (body, None) if body is not None else (None, "HTTP 503")
    return fetch


class Drought(unittest.TestCase):
    def test_stats(self):
        w = drought.parse_stats(STATS)
        self.assertEqual([x["map_date"] for x in w], ["2026-10-27", "2026-10-20"])
        self.assertEqual((w[0]["d1"], w[0]["d2"], w[0]["valid_end"]), (41.39, 22.36, "2026-11-02"))
        self.assertIn("startdate=09/14/2026&enddate=10/26/2026", drought.stats_url(NOW))

    def test_simplify(self):
        s = drought.simplify(json.loads(MAP))
        self.assertEqual([x["dm"] for x in s], [0, 2])
        d2 = s[1]["coordinates"]
        self.assertEqual(len(d2), 1)                                       # the speck is dropped
        self.assertEqual(d2[0][0][0], [-100.0, 35.0])                      # snapped to the 0.05-degree grid

    def test_map_only_for_a_new_week(self):
        seen = []
        rec, err = drought.collect({}, NOW, drought_fetch(STATS, MAP, seen))
        self.assertIsNone(err)
        self.assertEqual((rec["map_date"], len(seen)), ("2026-10-27", 2))
        seen.clear()
        rec2, err = drought.collect(rec, NOW, drought_fetch(STATS, MAP, seen))
        self.assertEqual(len(seen), 1)                                     # statistics only
        self.assertIs(rec2["polygons"], rec["polygons"])

    def test_map_failure_keeps_statistics(self):
        rec, err = drought.collect({}, NOW, drought_fetch(STATS, None, []))
        self.assertEqual(rec["weeks"][0]["map_date"], "2026-10-27")
        self.assertNotIn("polygons", rec)
        self.assertIn("map: HTTP 503", err)
        rec2, err2 = drought.collect({"weeks": ["old"]}, NOW, drought_fetch(None, None, []))
        self.assertEqual(rec2, {"weeks": ["old"]})

    def test_feed_item(self):
        rec, _ = drought.collect({}, NOW, drought_fetch(STATS, MAP, []))
        d = {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}
        d["usdm"] = {"records": rec, "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        regs = registers.ids(ROOT / "doctrine")
        for f in fc["features"]:
            self.assertEqual([m for _, sev, m in contract.check(f, regs) if sev == "error"], [])
        p = [f["properties"] for f in fc["features"] if f["properties"]["id"] == "elements:usdm:us"][0]
        self.assertEqual(p["title"], "US Drought Monitor, week of 27 Oct 2026: 41.4% of the US in drought, 22.4% severe or worse")
        self.assertEqual((p["measures"]["change_d2"], p["valid_until"]), (-1.62, "2026-11-02T12:00:00Z"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
