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


def gd(etype, eid, name, alert, episode_alert, sev_text, sev_value, unit="", lon=80.0, lat=15.0, current="true",
       country="India"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"eventtype": etype, "eventid": eid, "episodeid": 3, "name": name, "alertlevel": alert,
                           "episodealertlevel": episode_alert, "alertscore": 2, "fromdate": "2026-10-26T00:00:00",
                           "todate": "2026-10-28T06:00:00", "iscurrent": current, "country": country,
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

    def test_gdacs_text_sent_as_utf8_read_as_latin1_is_repaired(self):
        # GDACS's own JSON says "TÃ¼rkiye" for "Türkiye" (FL-1104292, 21 Nov 2026).
        doc = {"features": [gd("FL", 1104292, "Flood in TÃ¼rkiye", "Green", "Green", "Magnitude 0 ", 0.0, "",
                               37.4, 36.97, country="TÃ¼rkiye"),
                            gd("FL", 1104293, "Flood in Curaçao", "Green", "Green", "Magnitude 0 ", 0.0, "",
                               -68.9, 12.1, country="Curaçao")]}
        e = {x["id"]: x for x in sources.parse_gdacs(doc)}
        self.assertEqual(e["FL-1104292"]["name"], "Flood in Türkiye")
        self.assertEqual(e["FL-1104292"]["country"], "Türkiye")
        self.assertEqual(e["FL-1104292"]["countries"], ["TR"])
        self.assertEqual(e["FL-1104293"]["name"], "Flood in Curaçao", "text that is already right is left alone")
        d = {**dataset(), "gdacs": {"records": list(e.values()), "fetched_at": FETCHED}}
        fc = feed.build(d, NOW)
        p = next(f["properties"] for f in fc["features"] if f["properties"]["id"] == "elements:gdacs:FL-1104292")
        self.assertEqual(p["title"], "GDACS green alert: Flood in Türkiye")
        self.assertEqual(p["measures"]["name"], "Flood in Türkiye")

    def test_gdacs_event_carries_every_country_it_names(self):
        # DR-1027450 on 21 Nov 2026: the point is in Ethiopia, the text names thirteen countries.
        named = ("Burundi, Democratic Republic of Congo, Central African Republic, Cameroon, Eritrea, Ethiopia, Kenya, "
                 "Rwanda, Sudan, South Sudan, Chad, Tanzania, Uganda")
        doc = {"features": [
            gd("DR", 1027450, "Drought in " + named, "Orange", "Orange", "Medium impact", 1435673.0, "km2", 39.5, 6.5,
               country=named),
            gd("DR", 1018344, "Drought", "Green", "Green", "Low impact", 1.0, "km2", 11.5, -1.0,
               country="Angola, Democratic Republic of Congo, Republic of Congo, Cameroon, Gabon, Equatorial Guinea"),
            gd("DR", 1023877, "Drought", "Orange", "Orange", "Medium impact", 1.0, "km2", -66.0, 7.0,
               country="Aruba, , Brazil, French Guiana, Venezuela"),                 # an empty name, a territory
            gd("FL", 1104292, "Flood in TÃ¼rkiye", "Green", "Green", "Magnitude 0 ", 0.0, "", 37.4, 36.97,
               country="TÃ¼rkiye"),                                      # GDACS's UTF-8 read as Latin-1
            gd("TC", 1001350, "Tropical Cyclone", "Green", "Green", "Tropical Storm", 80.0, "km/h", -165.0, -15.0,
               country="Cook Islands, American Samoa"),                              # open sea under the point
            gd("FL", 1104291, "Flood in Iran", "Green", "Green", "Magnitude 0 ", 0.0, "", 51.9, 36.3,
               country="Islamic Republic of Iran, Atlantis"),                         # an unknown name is left out
        ]}
        e = {x["id"]: x for x in sources.parse_gdacs(doc)}
        dr = e["DR-1027450"]["countries"]
        self.assertEqual(dr[0], "ET")                       # the country under the point stays first
        self.assertEqual(sorted(dr), sorted(["ET", "BI", "CD", "CF", "CM", "ER", "KE", "RW", "SD", "SS", "TD", "TZ", "UG"]))
        self.assertEqual(len(dr), len(set(dr)))
        self.assertEqual(e["DR-1018344"]["countries"], ["GA", "AO", "CD", "CG", "CM", "GQ"])
        self.assertEqual(e["DR-1023877"]["countries"], ["VE", "AW", "BR", "FR"])
        self.assertEqual(e["FL-1104292"]["countries"], ["TR"])
        self.assertEqual(sorted(e["TC-1001350"]["countries"]), ["AS", "CK"])
        self.assertEqual(e["FL-1104291"]["countries"], ["IR"])
        # one name, no list: the point's country, as before
        self.assertEqual(sources.gdacs_countries("India", 86.0, 17.0), ["IN"])
        self.assertEqual(sources.gdacs_countries(None, 80.0, 15.0), ["IN"])
        self.assertEqual(sources.gdacs_countries("", -150.0, -30.0), [])

    def test_gdacs_countries_reach_the_feed(self):
        named = "Kenya, Ethiopia, Uganda"
        d = {**dataset(), "gdacs": {"records": sources.parse_gdacs({"features": [
            gd("DR", 1027450, "Drought in " + named, "Orange", "Orange", "Medium impact", 1.0, "km2", 39.5, 6.5,
               country=named)]}), "fetched_at": FETCHED}}
        fc = feed.build(d, NOW)
        p = next(f["properties"] for f in fc["features"] if f["properties"]["id"] == "elements:gdacs:DR-1027450")
        self.assertEqual(sorted(p["countries"]), ["ET", "KE", "UG"])

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

    def test_a_gdacs_end_date_after_the_fetch_is_not_the_data_time(self):
        # GDACS gives a running flood a todate of the next day's 01:00; Elements read 1.6 h ahead on 12 Nov 2026.
        d = dataset()
        rec = d["gdacs"]["records"][0]
        rec["to"] = "2026-11-01T01:00:00Z"
        fc = feed.build(d, NOW)
        p = next(f["properties"] for f in fc["features"] if f["properties"]["id"] == f"elements:gdacs:{rec['id']}")
        self.assertEqual(p["data_as_of"], FETCHED)
        self.assertEqual(p["measures"]["to"], "2026-11-01T01:00:00Z")
        past = next(f["properties"] for f in self.fc["features"] if f["properties"]["id"] == f"elements:gdacs:{rec['id']}")
        self.assertEqual(past["data_as_of"], "2026-10-28T06:00:00Z", "an end date before the fetch is kept")

    def test_an_ended_gdacs_event_leaves_the_feed_and_a_current_one_stays(self):
        # 23 Nov 2026: 36 of 48 GDACS items carried GDACS's own iscurrent=false (four anomaly-tier droughts among
        # them) and were shown as current. DR-1002 is an orange drought GDACS has ended; TC-1001 is current.
        d = dataset()
        dr = next(r for r in d["gdacs"]["records"] if r["id"] == "DR-1002")
        dr["current"] = False
        gone = []
        fc = feed.build(d, NOW, ended=gone)
        ids = {f["properties"]["id"] for f in fc["features"]}
        self.assertNotIn("elements:gdacs:DR-1002", ids)
        self.assertIn("elements:gdacs:TC-1001", ids)
        self.assertEqual([f["properties"]["id"] for f in gone], ["elements:gdacs:DR-1002"])
        g = gone[0]["properties"]
        self.assertEqual((g["tier"], g["measures"]["current"], g["valid_until"]), ("routine", False, "2026-10-28T06:00:00Z"))
        self.assertNotIn("baseline_ref", g)
        self.assertEqual(g["event_end"], "2026-10-28T06:00:00Z")
        regs = registers.ids(ROOT / "doctrine")
        self.assertEqual([m for _, sev, m in contract.check(gone[0], regs) if sev == "error"], [])
        tc = next(f["properties"] for f in fc["features"] if f["properties"]["id"] == "elements:gdacs:TC-1001")
        self.assertEqual((tc["tier"], tc["valid_until"]), ("anomaly", "2026-11-04T06:00:00Z"))  # to + 7 days
        self.assertNotIn("anomaly", [f["properties"]["tier"] for f in gone])

    def test_a_current_gdacs_event_with_no_report_for_a_week_counts_as_ended(self):
        e = {"current": True, "to": "2026-10-24T21:00:00Z"}
        self.assertTrue(feed.gdacs_ended(e, NOW))
        self.assertFalse(feed.gdacs_ended({**e, "to": "2026-10-25T00:00:00Z"}, NOW))
        self.assertFalse(feed.gdacs_ended({"current": True, "to": None}, NOW))
        self.assertTrue(feed.gdacs_ended({"current": False, "to": "2026-11-01T01:00:00Z"}, NOW))

    def test_a_gdacs_event_does_not_age_out_while_gdacs_is_not_read(self):
        # The lane last read GDACS on 31 Oct (FETCHED); the build runs on 5 Nov from that copy. TC-1001's latest report
        # (28 Oct 06:00) is more than a week before the build but not before the read: no read has shown GDACS
        # stopped reporting it, so it stays, as the copy's other events do. GDACS's own iscurrent=false still ends one.
        later = datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)
        d = dataset()
        next(r for r in d["gdacs"]["records"] if r["id"] == "DR-1002")["current"] = False
        gone = []
        ids = {f["properties"]["id"] for f in feed.build(d, later, ended=gone)["features"]}
        self.assertIn("elements:gdacs:TC-1001", ids)
        self.assertEqual([f["properties"]["id"] for f in gone], ["elements:gdacs:DR-1002"])
        d["gdacs"]["fetched_at"] = "2026-11-04T23:56:00Z"          # a good read on 4-5 Nov with no later report
        gone = []
        ids = {f["properties"]["id"] for f in feed.build(d, later, ended=gone)["features"]}
        self.assertNotIn("elements:gdacs:TC-1001", ids)
        self.assertIn("elements:gdacs:TC-1001", [f["properties"]["id"] for f in gone])

    def test_the_history_step_logs_the_ended_gdacs_version(self):
        import importlib.util
        from elements import history
        spec = importlib.util.spec_from_file_location("elements_tool", ROOT / "tools" / "elements.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        before = feed.build(dataset(), NOW)                       # the run before: DR-1002 current
        state, _ = history.update({}, before, None, NOW)
        d = dataset()
        next(r for r in d["gdacs"]["records"] if r["id"] == "DR-1002")["current"] = False
        gone = []
        fc = feed.build(d, NOW, ended=gone)
        self.assertEqual(tool.keep_ended_version(state, gone), 1)
        state, lines = history.update(state, fc, None, NOW)
        end = [x for x in lines if x["change"] == "ended"]
        self.assertEqual([x["id"] for x in end], ["elements:gdacs:DR-1002"])
        self.assertIs(end[0]["item"]["properties"]["measures"]["current"], False)
        self.assertEqual(end[0]["peak_tier"], "anomaly", "the record keeps the tier it reached")
        self.assertNotIn("elements:gdacs:DR-1002", state["open"])

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

    def test_a_satellite_with_no_rows_is_named(self):
        # Suomi-NPP's data delivery ended on 2 Nov 2026; its public files have been header-only (112 bytes) since 12 Nov.
        seen = []
        def fetch(url, timeout=40, max_bytes=None):
            seen.append(url)
            if "mapkey_status" in url:
                return json.dumps({"transaction_limit": 5000, "current_transactions": 6}).encode(), None
            return (FIRMS_HEAD.encode() if "VIIRS_SNPP_NRT" in url else firms_csv(FIRE_ROWS, "letter")), None
        with patch.dict(os.environ, {"FIRMS_MAP_KEY": KEY}):
            p, err = firms.collect_firms(None, NOW, fetch)
        self.assertIsNone(err, "a header-only answer is a good read, not a failure")
        self.assertEqual(p["via"], {"VIIRS_NOAA20_NRT": "api", "VIIRS_NOAA21_NRT": "api", "VIIRS_SNPP_NRT": "api (no rows)"})
        self.assertEqual(p["rows"]["VIIRS_SNPP_NRT"], 0)
        self.assertEqual(p["rows"]["VIIRS_NOAA20_NRT"], len(FIRE_ROWS))
        s = firms.summary(p)
        self.assertIn("cells via api; no rows from Suomi-NPP; key used 6 of 5000 transactions", s)
        self.assertNotIn(KEY, s + json.dumps(p))
        with patch.dict(os.environ, {"FIRMS_MAP_KEY": ""}):
            p, _ = firms.collect_firms(None, NOW, lambda url, *a: ((FIRMS_HEAD.encode() if "SUOMI" in url
                                                                     else firms_csv(FIRE_ROWS)), None))
        self.assertEqual(p["via"]["VIIRS_SNPP_NRT"], "public files (no rows)")
        self.assertIn("via public files; no rows from Suomi-NPP", firms.summary(p))

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

    def test_daily_counts_have_no_cap(self):
        days = {f"2024-{m:02d}-{d:02d}": {"BR": 1} for m in range(1, 13) for d in range(1, 29)}
        days.update({f"2025-{m:02d}-{d:02d}": {"BR": 1} for m in range(1, 13) for d in range(1, 29)})
        self.assertGreater(len(days), 600)
        a = firms.aggregate(firms.parse(firms_csv(FIRE_ROWS)), NOW)
        h = firms.update_history({"days": days}, a, "2026-10-31")
        self.assertTrue(set(days) <= set(h["days"]))
        self.assertFalse(hasattr(firms, "KEEP_DAYS"))

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

    def test_feed_fire_baseline(self):
        # 28-day median; anomaly at 3 times it and at least 50; routine under 14 days of history.
        from datetime import date, timedelta
        today = NOW.date()
        days = {(today - timedelta(days=i)).isoformat(): {"BR": 100, "GR": 0} for i in range(1, 21)}
        days[(today - timedelta(days=1)).isoformat()]["AR"] = 5
        days[today.isoformat()] = {"BR": 9999}                  # today is still filling: not in the baseline
        cell = lambda n, cc: [-50.0, -10.0, n, n, 30.0, 9.0, "2026-10-31T15:30Z", cc]
        d = dataset()
        d["firms_climatology"] = None                            # no seasonal record: the 28-day rule alone
        d["firms_daily"] = {"days": days}
        d["firms"] = {"records": {"cells": [cell(300, "BR"), cell(60, "GR"), cell(40, "AR")], "window": [None, None],
                                  "cell_deg": 0.5}, "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        fire = {f["properties"]["id"]: f["properties"] for f in fc["features"] if f["properties"]["id"].startswith("elements:firms:")}
        br, gr, ar = fire["elements:firms:BR"], fire["elements:firms:GR"], fire["elements:firms:AR"]
        self.assertEqual((br["tier"], br["signal"]["expected"], br["signal"]["baseline_n"]), ("anomaly", 100, 20))
        self.assertEqual((br["baseline_ref"]["id"], br["baseline_ref"]["type"]), ("firms-country-median", "rolling"))
        self.assertEqual(gr["tier"], "anomaly")                  # median 0, 60 detections: over the floor of 50
        self.assertEqual(ar["tier"], "routine")                  # under the floor of 50
        d["firms"]["records"]["cells"][0] = cell(299, "BR")
        self.assertEqual({f["properties"]["id"]: f["properties"]["tier"] for f in feed.build(d, NOW)["features"]}["elements:firms:BR"], "routine")
        d["firms_daily"] = {"days": dict(sorted(days.items())[-14:])}   # 13 complete days and today
        fc = feed.build(d, NOW)
        br = [f["properties"] for f in fc["features"] if f["properties"]["id"] == "elements:firms:BR"][0]
        self.assertEqual(br["tier"], "routine")
        self.assertNotIn("expected", br["signal"])
        self.assertNotIn("baseline_ref", br)

    @staticmethod
    def clim(values, first="2020-01-01", last="2025-12-31", gaps=()):
        """A climatology like catalog/firms_climatology.json.gz: values(day) is a country's NOAA-20 count."""
        from datetime import date, timedelta
        a, b = date.fromisoformat(first), date.fromisoformat(last)
        days = [(a + timedelta(i)).isoformat() for i in range((b - a).days + 1)]
        return {"first": first, "last": last, "gaps": list(gaps),
                "countries": {cc: [None if d in gaps else f(d) for d in days] for cc, f in values.items()}}

    def test_fire_percentile(self):
        # Nearest rank: no more than 5% of the readings are above the 95th percentile.
        self.assertEqual(feed._percentile([4, 1, 3, 2], 50), 2)
        self.assertEqual(feed._percentile(list(range(1, 11)), 95), 10)
        self.assertEqual(feed._percentile(list(range(1, 21)), 95), 19)
        self.assertEqual(feed._percentile(list(range(1, 156)), 95), 148)   # 7 of 155 above: 4.5%
        self.assertEqual(feed._percentile([7], 95), 7)

    def test_fire_seasonal(self):
        # 95th percentile of the same +-15-day window in each earlier year, times 2 for two satellites.
        c = self.clim({"GH": lambda d: 100 if d[5:7] == "11" else 10})
        s = feed.fire_seasonal(c, "GH", "2026-11-20")                # window 5 Nov-5 Dec: 26 days of 100, 5 of 10
        self.assertEqual((s["threshold"], s["first_year"], s["last_year"], s["years"], s["readings"]),
                         (200.0, 2020, 2025, 6, 186))
        self.assertEqual(s["flag_rate"], 0.0)
        self.assertEqual(feed.fire_seasonal(c, "GH", "2026-07-01")["threshold"], 20.0)
        self.assertEqual(feed.fire_seasonal(c, "GH", "2023-11-20")["years"], 3)   # earlier years only
        self.assertIsNone(feed.fire_seasonal(c, "GH", "2022-11-20"))             # 2 earlier years: too few
        self.assertIsNone(feed.fire_seasonal(c, "BR", "2026-11-20"))             # no record for the country
        self.assertIsNone(feed.fire_seasonal(None, "GH", "2026-11-20"))
        self.assertEqual(feed.fire_seasonal(c, "GH", "2028-02-29")["years"], 6)  # 29 Feb matched with 28 Feb
        gap = [f"2021-11-{k:02d}" for k in range(1, 31)]                         # most of 2021's window missing
        g = self.clim({"GH": lambda d: 100 if d[5:7] == "11" else 10}, gaps=gap)
        self.assertEqual(feed.fire_seasonal(g, "GH", "2026-11-20")["years"], 5)
        r = self.clim({"GH": lambda d: int(d[8:10])})                            # 1..31: the top 5% are above
        self.assertLessEqual(feed.fire_seasonal(r, "GH", "2026-11-20")["flag_rate"], 0.05)

    def test_feed_fire_seasonal(self):
        # elements-feed-1.3: 3 times the 28-day median and the floor, and above the seasonal threshold.
        from datetime import timedelta
        today = NOW.date()
        days = {(today - timedelta(days=i)).isoformat(): {"GH": 30, "TG": 100, "BR": 30} for i in range(1, 21)}
        cell = lambda n, cc: [-1.0, 7.0, n, n, 30.0, 9.0, "2026-10-31T15:30Z", cc]
        d = dataset()
        d["firms_climatology"] = self.clim({"GH": lambda x: 100 if x[5:7] in ("10", "11") else 10,
                                            "TG": lambda x: 10})
        d["firms_daily"] = {"days": days}

        def tiers(cells):
            d["firms"] = {"records": {"cells": cells, "window": [None, None], "cell_deg": 0.5}, "fetched_at": FETCHED}
            fc = feed.build(d, NOW)
            self.assertEqual(fc["dropped"], [])
            return {f["properties"]["countries"][0]: f["properties"] for f in fc["features"]
                    if f["properties"]["id"].startswith("elements:firms:")}

        f = tiers([cell(150, "GH"), cell(250, "TG"), cell(150, "BR")])
        gh, tg, br = f["GH"], f["TG"], f["BR"]
        # The season's onset: 5 times its 28-day median, but usual for the season (threshold 2 x 100). Under
        # elements-feed-1.2 this was an anomaly.
        self.assertEqual(gh["tier"], "routine")
        self.assertIn("usual for the season", gh["measures"]["held_routine"])
        self.assertEqual((gh["measures"]["seasonal_threshold"], gh["measures"]["seasonal_years"]), (200.0, 6))
        self.assertEqual((gh["baseline_ref"]["id"], gh["baseline_ref"]["type"], gh["baseline_ref"]["flag_rate"]),
                         ("firms-country-seasonal", "both", 0.0))
        self.assertIn("2020-2025", gh["baseline_ref"]["window"])
        self.assertEqual(gh["signal"]["expected"], 30)
        self.assertEqual(tg["tier"], "routine")          # above its season (20) but under 3 x its median of 100
        self.assertNotIn("held_routine", tg["measures"])
        self.assertEqual(br["tier"], "anomaly")          # no seasonal record: the 28-day rule alone
        self.assertEqual(br["baseline_ref"]["id"], "firms-country-median")
        self.assertEqual(tiers([cell(201, "GH")])["GH"]["tier"], "anomaly")   # above both
        self.assertEqual(tiers([cell(200, "GH")])["GH"]["tier"], "routine")   # at the threshold is not above it
        self.assertEqual(tiers([cell(49, "TG")])["TG"]["tier"], "routine")    # under the floor of 50

    def test_fire_climatology_file(self):
        # The committed record: NOAA-20 from 1 Apr 2018, the archive's gap days null, and the Evros fire of
        # August 2023 above Greece's seasonal threshold.
        c = feed.fire_climatology()
        self.assertGreaterEqual(len(c["countries"]), 200)
        self.assertEqual(c["first"], "2018-04-01")
        self.assertTrue({"2023-07-19", "2023-07-22", "2023-09-30", "2024-02-04"} <= set(c["gaps"]))
        from datetime import date
        i = (date(2023, 8, 22) - date(2018, 4, 1)).days
        self.assertIsNone(c["countries"]["GR"][(date(2023, 7, 20) - date(2018, 4, 1)).days])
        s = feed.fire_seasonal(c, "GR", "2023-08-22")
        self.assertGreater(c["countries"]["GR"][i] * feed.FIRE_CLIM_SATS, s["threshold"])
        self.assertLessEqual(s["flag_rate"], 0.05)

    def test_feed_floor_keeps_open_items(self):
        # An open country item stays down to 5 detections; a new one still needs 10.
        d = dataset()
        cells = [[-50.0, -10.0, 6, 6, 30.0, 9.0, "2026-10-31T15:30Z", "BR"],
                 [121.0, 23.7, 6, 6, 30.0, 9.0, "2026-10-31T15:30Z", "TW"],
                 [30.0, 0.0, 4, 4, 10.0, 3.0, "2026-10-31T15:30Z", "UG"]]
        d["firms"] = {"records": {"cells": cells, "window": [None, None], "cell_deg": 0.5}, "fetched_at": FETCHED}
        ids = lambda fc: sorted(f["properties"]["id"] for f in fc["features"] if f["properties"]["id"].startswith("elements:firms:"))
        self.assertEqual(ids(feed.build(d, NOW)), [])
        held = {"elements:firms:BR", "elements:firms:UG"}
        self.assertEqual(ids(feed.build(d, NOW, open_ids=held)), ["elements:firms:BR"])
        self.assertEqual(ids(feed.build(d, NOW, state={"open": {k: {"first_seen": "2026-10-31T00:00:00Z"} for k in held}})), ["elements:firms:BR"])

    def test_country_names_and_taiwan(self):
        from elements.common import country_at, country_name
        self.assertEqual(country_at(23.7, 121.0), "TW")
        self.assertEqual(country_name("TW"), "Taiwan")
        self.assertEqual(country_name("SS"), "South Sudan")
        self.assertEqual(country_name("BR"), "Brazil")


class Registers(unittest.TestCase):
    def test_registers_valid(self):
        self.assertEqual(registers.check(ROOT / "doctrine"), [])

    def test_area_menu_states(self):
        # The Area menu (tic-area.js; Tom, 16 Nov 2026): every state with a name and boxes; Alaska gets one box per
        # side of 180 degrees, so its Aleutians do not make a box around the world.
        import importlib.util
        spec = importlib.util.spec_from_file_location("elements_tool", ROOT / "tools" / "elements.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        by = {s["code"]: s for s in tool.states_json()["states"]}
        self.assertTrue({"US-MN", "US-ND", "US-HI", "US-AK", "US-DC"} <= set(by))
        self.assertEqual(len(by["US-AK"]["boxes"]), 2)
        w, s, e, n = by["US-HI"]["boxes"][0]
        self.assertTrue(w < -155.28 < e and s < 19.41 < n)  # Kilauea is in Hawaii's box
        self.assertTrue(all(len(b) == 4 for st in by.values() for b in st["boxes"]))


class TownCountry(unittest.TestCase):
    def test_place_text(self):
        tc = feed.town_country
        self.assertEqual(tc("85 km S of Gorontalo, Indonesia"), "ID")
        self.assertEqual(tc("207 km ESE of Sarangani, Philippines"), "PH")
        self.assertEqual(tc("74 km E of Petropavlovsk-Kamchatsky, Russia"), "RU")
        self.assertEqual(tc("12 km SW of Adak, Alaska"), "US")
        self.assertEqual(tc("5.3 km NNE of Ridgecrest, CA"), "US")
        self.assertIsNone(tc("Fiji region"))
        self.assertIsNone(tc("Volcano Islands, Japan region"))
        self.assertIsNone(tc("south of the Fiji Islands"))
        self.assertIsNone(tc(None))

    def test_georgia_by_hemisphere(self):
        # "Georgia" names both a US state and a country: the epicentre's longitude decides which
        tc = feed.town_country
        self.assertEqual(tc("20 km W of Poti, Georgia", lon=41.4), "GE")          # Black Sea
        self.assertEqual(tc("30 km SE of Savannah, Georgia", lon=-80.9), "US")    # off the US Atlantic coast
        self.assertIsNone(tc("20 km W of Poti, Georgia"))                         # no longitude: no guess
        self.assertEqual(tc("12 km SW of Adak, Alaska", lon=-176.7), "US")        # other states unchanged
        self.assertEqual(tc("85 km S of Gorontalo, Indonesia", lon=123.0), "ID")

    def test_offshore_georgia_in_the_feed(self):
        def placed(eid, lon, lat, place):
            q = quake(eid, 4.8, lon, lat)
            q["properties"]["place"] = place
            return q
        recs = sources.parse_usgs({"type": "FeatureCollection", "features": [
            placed("usge", 41.42, 42.15, "20 km W of Poti, Georgia"),            # Black Sea, in no country
            placed("usga", -80.85, 31.9, "30 km SE of Savannah, Georgia")]})     # US Atlantic shelf, in no country
        self.assertEqual([r["countries"] for r in recs], [[], []])
        fc = feed.build({**dataset(), "usgs": {"records": recs, "fetched_at": FETCHED}}, NOW)
        tc = {f["properties"]["id"]: f["properties"]["measures"].get("town_country") for f in fc["features"]}
        self.assertEqual(tc["elements:usgs:usge"], "GE")
        self.assertEqual(tc["elements:usgs:usga"], "US")


if __name__ == "__main__":
    unittest.main(verbosity=1)
