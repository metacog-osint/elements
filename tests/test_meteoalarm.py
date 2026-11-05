"""Offline tests for Elements' European weather-warning lane (MeteoAlarm). Fixtures copy the live format of
feeds.meteoalarm.org/api/v1/warnings/feeds-{country} on 5 Nov 2026 (trimmed), and the region points in
catalog/meteoalarm_areas.json."""
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, meteoalarm  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402

# tools/elements.py shares its name with the package, so load it under another name (for warnings_map)
_spec = importlib.util.spec_from_file_location("elements_cli", ROOT / "tools" / "elements.py")
elements_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(elements_cli)

NOW = datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc)
FETCHED = "2026-11-05T18:58:00Z"


def info(lang, level, kind, areas, onset="2026-11-05T18:00:00+01:00", expires="2026-11-06T06:00:00+01:00",
         sender="Deutscher Wetterdienst", event="wind", headline="Official WARNING of WIND GUSTS", response="Prepare",
         licence=None):
    codes = [{"value": "2.1.14", "valueName": "PROFILE_VERSION"}]
    if licence:
        codes.append({"value": licence, "valueName": "LICENSE"})
    return {"language": lang, "category": ["Met"], "event": event, "headline": headline, "senderName": sender,
            "severity": {2: "Moderate", 3: "Severe", 4: "Extreme", 1: "Minor"}[level], "urgency": "Immediate",
            "certainty": "Likely", "onset": onset, "expires": expires, "responseType": [response], "eventCode": codes,
            "web": "https://www.dwd.de/warnungen",
            "parameter": [{"value": f"{level}; {meteoalarm.LEVELS.get(level, 'green')}; x", "valueName": "awareness_level"},
                          {"value": kind, "valueName": "awareness_type"}],
            **({"area": areas} if areas is not None else {})}


def alert(ident, infos, sent="2026-11-05T17:50:00+01:00", refs=None, msg="Alert"):
    a = {"identifier": ident, "sender": "opendata@dwd.de", "sent": sent, "status": "Actual", "msgType": msg,
         "scope": "Public", "incidents": "Alert", "info": infos}
    if refs:
        a["references"] = refs
    return {"alert": a, "uuid": ident[-8:]}


LAHN = {"areaDesc": "Lahn-Dill-Kreis", "geocode": [{"value": "DE395", "valueName": "EMMA_ID"}]}
POLY = {"areaDesc": "Saaristomeri", "polygon": ["60.0,21.0 60.0,22.0 60.5,22.0 60.5,21.0 60.0,21.0"]}

GERMANY = {"warnings": [
    # orange wind: an update whose chain starts at an earlier message, kept under the earlier id
    alert("2.49.0.0.276.0.DWD.B", [info("de-DE", 3, "1; Wind", [LAHN], event="STURMBÖEN"),
                                    info("en-GB", 3, "1; Wind", [LAHN], licence="© GeoBasis-DE / BKG 2021 (Daten modifiziert)")],
          sent="2026-11-05T18:20:00+01:00", msg="Update",
          refs="opendata@dwd.de,2.49.0.0.276.0.DWD.A,2026-11-05T16:00:00+01:00"),
    # yellow fog, starts tomorrow: kept
    alert("2.49.0.0.276.0.DWD.C", [info("en-GB", 2, "4; Fog", [LAHN], onset="2026-11-06T05:00:00+01:00",
                                         expires="2026-11-06T10:00:00+01:00", event="fog")]),
    # green: not kept
    alert("2.49.0.0.276.0.DWD.D", [info("en-GB", 1, "1; Wind", [LAHN])]),
    # all-clear update: not kept
    alert("2.49.0.0.276.0.DWD.E", [info("en-GB", 2, "4; Fog", [LAHN], response="AllClear")], msg="Update",
          refs="opendata@dwd.de,2.49.0.0.276.0.DWD.Z,2026-11-05T06:00:00+01:00"),
    # expired before NOW: not kept
    alert("2.49.0.0.276.0.DWD.F", [info("en-GB", 3, "10; Rain", [LAHN], expires="2026-11-05T19:00:00+01:00")]),
]}

FRANCE = {"warnings": [
    # red rain-flood; France names departments by NUTS3 code only: placed by name ("Corse-du-Sud" = "Corse du Sud")
    alert("2.49.0.0.250.0.FR.R", [info("fr-FR", 4, "13; rain-flood", None, sender="METEO-FRANCE"),
                                   info("en-GB", 4, "13; rain-flood", [
                                       {"areaDesc": "Corse-du-Sud", "geocode": [{"value": "FRM01", "valueName": "NUTS3"}]},
                                       {"areaDesc": "Haute-Corse", "geocode": [{"value": "FRM02", "valueName": "NUTS3"}]}],
                                        sender="METEO-FRANCE", event="Red flood warning")]),
    # an area MeteoAlarm's table does not know: the country point, and the item says so
    alert("2.49.0.0.250.0.FR.S", [info("en-GB", 3, "3; Thunderstorm", [
        {"areaDesc": "Somewhere new", "geocode": [{"value": "FR999", "valueName": "EMMA_ID"}]}], sender="METEO-FRANCE")]),
    # no areas in any language block: the country point
    alert("2.49.0.0.250.0.FR.T", [info("en-GB", 2, "1; Wind", None, sender="METEO-FRANCE")]),
]}

FINLAND = {"warnings": [
    alert("2.49.0.0.246.0.FI.P", [info("en-GB", 2, "14; Marine-Hazard", [POLY], sender="Finnish Meteorological Institute")]),
]}


def parse_all():
    return (meteoalarm.parse(GERMANY, "germany", NOW) + meteoalarm.parse(FRANCE, "france", NOW)
            + meteoalarm.parse(FINLAND, "finland", NOW))


class Geometry(unittest.TestCase):
    def test_polygon_text(self):
        self.assertEqual(meteoalarm.parse_polygon("60.0,21.0 60.0,22.0 60.5,22.0"),
                         [[21.0, 60.0], [22.0, 60.0], [22.0, 60.5], [21.0, 60.0]])   # lon, lat; ring closed
        self.assertIsNone(meteoalarm.parse_polygon("60.0,21.0 60.0"))
        self.assertIsNone(meteoalarm.parse_polygon("60.0,21.0 60.1,21.1"))

    def test_point_inside_u_shape_and_hole(self):
        u = [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]]   # centroid falls in the gap
        x, y = meteoalarm.rep_point([[u]])
        self.assertTrue(meteoalarm._inside(x, y, u), (x, y))
        square, hole = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]], [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]
        x, y = meteoalarm.rep_point([[square, hole]])
        self.assertTrue(meteoalarm._inside(x, y, square) and not meteoalarm._inside(x, y, hole), (x, y))
        self.assertIsNone(meteoalarm.rep_point([]))


class Parse(unittest.TestCase):
    def setUp(self):
        self.r = {r["identifier"]: r for r in parse_all()}

    def test_keeps_yellow_to_red_in_force(self):
        self.assertEqual(sorted(self.r), ["2.49.0.0.246.0.FI.P", "2.49.0.0.250.0.FR.R", "2.49.0.0.250.0.FR.S",
                                          "2.49.0.0.250.0.FR.T", "2.49.0.0.276.0.DWD.B", "2.49.0.0.276.0.DWD.C"])
        b = self.r["2.49.0.0.276.0.DWD.B"]
        self.assertEqual((b["colour"], b["type"], b["country"], b["event"]), ("orange", "wind", "DE", "wind"))  # English block
        self.assertEqual((b["onset"], b["expires"], b["sent"]), ("2026-11-05T17:00:00Z", "2026-11-06T05:00:00Z", "2026-11-05T17:20:00Z"))
        self.assertEqual(b["credit"], "© GeoBasis-DE / BKG 2021 (Daten modifiziert)")
        self.assertEqual(self.r["2.49.0.0.276.0.DWD.C"]["onset"], "2026-11-06T04:00:00Z")   # starts tomorrow, still kept

    def test_one_id_across_updates(self):
        import hashlib
        self.assertEqual(self.r["2.49.0.0.276.0.DWD.B"]["id"], hashlib.sha1(b"2.49.0.0.276.0.DWD.A").hexdigest()[:12])
        older = alert("2.49.0.0.276.0.DWD.A", [info("en-GB", 2, "1; Wind", [LAHN])], sent="2026-11-05T16:00:00+01:00")
        got = meteoalarm.parse({"warnings": [older] + GERMANY["warnings"][:1]}, "germany", NOW)
        self.assertEqual([(r["identifier"], r["colour"]) for r in got], [("2.49.0.0.276.0.DWD.B", "orange")])   # the later message

    def test_places(self):
        b = self.r["2.49.0.0.276.0.DWD.B"]
        self.assertEqual((b["points"], b["precision"], b["polygons"], b["placed"]), ([[8.378, 50.641]], "approximate", None, {"region": 1}))
        red = self.r["2.49.0.0.250.0.FR.R"]
        self.assertEqual((red["points"], red["precision"]), ([[8.986, 41.869], [9.206, 42.395]], "approximate"))
        new = self.r["2.49.0.0.250.0.FR.S"]
        self.assertEqual((new["precision"], new["placed"]), ("country", {"country": 1}))
        self.assertEqual(len(new["points"]), 1)
        self.assertEqual(self.r["2.49.0.0.250.0.FR.T"]["precision"], "country")
        fi = self.r["2.49.0.0.246.0.FI.P"]
        self.assertEqual((fi["precision"], fi["polygons"][0][0][0], fi["type"]), ("area", [21.0, 60.0], "marine hazard"))

    def test_collect_keeps_a_failed_country_until_expiry(self):
        old = [{"id": "x", "feed": "spain", "expires": "2026-11-06T00:00:00Z", "level": 2, "country": "ES", "onset": None},
               {"id": "y", "feed": "spain", "expires": "2026-11-05T18:00:00Z", "level": 2, "country": "ES", "onset": None}]

        def fake(url, timeout=40, max_bytes=None):
            if url.endswith("germany"):
                return json.dumps(GERMANY).encode(), None
            if url.endswith("france"):
                return b"not json", None
            return None, "HTTP 503"
        got, err = meteoalarm.collect(old, NOW, fake, feeds=["germany", "france", "spain"])
        self.assertEqual(sorted(r["id"] for r in got if r["feed"] == "spain"), ["x"])   # y has expired
        self.assertEqual(len([r for r in got if r["feed"] == "germany"]), 2)
        self.assertTrue(err.startswith("2 of 3 countries failed") and "france: parse" in err and "spain: HTTP 503" in err, err)
        self.assertEqual(got[0]["colour"], "orange")   # worst first
        stale = [{"id": "z", "feed": "germany", "expires": "2026-11-05T18:00:00Z", "level": 2, "country": "DE"}]
        none, err = meteoalarm.collect(stale, NOW, lambda *a, **k: (None, "HTTP 500"), feeds=["germany"])
        self.assertEqual((none, err[:20]), (stale, "every country failed"))   # the build then drops it as expired

    def test_summary(self):
        self.assertEqual(meteoalarm.summary(parse_all()), "6 warnings in force in 3 countries (yellow 3, orange 2, red 1)")


class Feed(unittest.TestCase):
    def build(self, now=NOW):
        d = {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}
        d["meteoalarm"] = {"records": parse_all(), "fetched_at": FETCHED}
        return feed.build(d, now)

    def test_items(self):
        fc = self.build()
        self.assertEqual(fc["dropped"], [])
        regs = registers.ids(ROOT / "doctrine")
        for f in fc["features"]:
            self.assertEqual([m for _, sev, m in contract.check(f, regs) if sev == "error"], [], f["properties"]["id"])
        by = {f["properties"]["id"]: f for f in fc["features"]}
        ids = sorted(by)
        self.assertEqual(len([i for i in ids if i.endswith(":in-force")]), 3)   # Germany, France, Finland
        self.assertEqual(len([i for i in ids if not i.endswith(":in-force")]), 3)   # two orange, one red
        red = next(f["properties"] for f in by.values() if f["properties"]["measures"].get("awareness_level") == "red")
        self.assertEqual((red["tier"], red["baseline_ref"]["id"], red["requirement_ids"]), ("anomaly", "meteoalarm-awareness", ["EL-PIR-11"]))
        self.assertEqual(red["title"], "Red rain and flooding warning for Corse-du-Sud; Haute-Corse (METEO-FRANCE)")
        self.assertEqual(red["sources"][0]["publisher"], "METEO-FRANCE via MeteoAlarm (EUMETNET)")
        de = by["elements:meteoalarm:de:" + meteoalarm.parse(GERMANY, "germany", NOW)[0]["id"]]
        self.assertEqual((de["properties"]["tier"], de["geometry"]["type"], de["properties"]["valid_until"]),
                         ("routine", "MultiPoint", "2026-11-06T05:00:00Z"))
        cc = by["elements:meteoalarm:de:in-force"]["properties"]
        self.assertEqual((cc["measures"]["warnings"], cc["measures"]["yellow"], cc["measures"]["orange"]), (2, 1, 1))
        self.assertEqual(cc["title"], "2 weather warnings in force in Germany (1 orange, 1 yellow), most for fog (MeteoAlarm)")
        self.assertEqual(by["elements:meteoalarm:fi:in-force"]["properties"]["title"],
                         "1 weather warning in force in Finland (1 yellow), most for marine hazard (MeteoAlarm)")

    def test_expired_by_build_time_are_left_out(self):
        fc = self.build(datetime(2026, 11, 6, 6, 0, tzinfo=timezone.utc))   # Germany's orange ended at 05:00Z
        ids = [f["properties"]["id"] for f in fc["features"]]
        de = [i for i in ids if i.startswith("elements:meteoalarm:de:")]
        self.assertEqual(de, ["elements:meteoalarm:de:in-force"])   # only the fog warning, yellow, remains

    def test_map_file(self):
        m = elements_cli.warnings_map({"records": parse_all(), "fetched_at": FETCHED}, NOW)
        self.assertEqual([w["colour"] for w in m["warnings"]], ["yellow", "yellow", "yellow", "orange", "orange", "red"])
        self.assertEqual(m["names"], {"DE": "Germany", "FI": "Finland", "FR": "France"})
        later = elements_cli.warnings_map({"records": parse_all()}, datetime(2026, 11, 7, tzinfo=timezone.utc))
        self.assertEqual(later["warnings"], [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
