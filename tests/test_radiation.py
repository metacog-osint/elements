"""Offline tests for Elements' NRC lanes (method elements-feed-1.2): event notifications with their emergency classes,
and the daily power reactor status. Fixtures in tests/fixtures/nrc/ (MANIFEST.json says which are cut from real NRC
pages and which are rebuilt from values read on 25 Nov 2026); the shutdown cases are synthetic."""
import importlib.util
import json
import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, nrc  # noqa: E402
from tic_doctrine import contract, geo, registers  # noqa: E402

_spec = importlib.util.spec_from_file_location("elements_cli", ROOT / "tools" / "elements.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

FIX = ROOT / "tests" / "fixtures" / "nrc"
NOW = datetime(2026, 2, 24, 15, 0, tzinfo=timezone.utc)
FETCHED = "2026-02-24T14:56:00Z"
LANES = ["usgs", "gdacs", "nhc", "cems", "firms", "usgs_volcano", "nws", "spc", "tsunami", "usdm", "meteoalarm",
         "emsc", "nifc"]


def text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def report(name: str, ymd: str) -> list[dict]:
    return nrc.parse_report(text(name), ymd)


def series(units: dict, newest: str, days: int = 31) -> list[dict]:
    """Status records, newest first: units maps a unit name to a function of the day's age (0 = newest)."""
    d0 = datetime.fromisoformat(newest)
    return [{"date": (d0 - timedelta(days=i)).strftime("%Y-%m-%d"), "units": {u: f(i) for u, f in units.items()}}
            for i in range(days)]


def build(events=(), status=(), now=NOW):
    d = {k: {"records": [], "fetched_at": FETCHED} for k in LANES}
    d["firms"]["records"], d["usdm"]["records"] = {}, {}
    d["nrc_events"] = {"records": list(events), "fetched_at": FETCHED}
    d["nrc_status"] = {"records": list(status), "fetched_at": FETCHED}
    d["health"] = {}
    return feed.build(d, now)


def items(fc, kind):
    return {x["properties"]["id"]: x for x in fc["features"] if x["properties"]["id"].startswith(f"elements:{kind}:")}


class Times(unittest.TestCase):
    def test_eastern_time_follows_daylight_time(self):
        self.assertEqual(nrc.to_utc("02/23/2026", "03:02", "ET"), "2026-02-23T08:02:00Z")
        self.assertEqual(nrc.to_utc("07/04/2026", "12:00", "ET"), "2026-07-04T16:00:00Z")
        # 2026: daylight time from 8 Mar 02:00 to 1 Nov 02:00 local
        self.assertEqual(nrc.to_utc("03/08/2026", "01:59", "ET"), "2026-03-08T06:59:00Z")
        self.assertEqual(nrc.to_utc("03/08/2026", "03:00", "ET"), "2026-03-08T07:00:00Z")
        self.assertEqual(nrc.to_utc("11/01/2026", "02:30", "ET"), "2026-11-01T07:30:00Z")

    def test_fixed_zones_and_unknown_ones(self):
        self.assertEqual(nrc.to_utc("01/09/2012", "14:05", "PST"), "2012-01-09T22:05:00Z")
        self.assertEqual(nrc.to_utc("07/01/2026", "10:00", "CDT"), "2026-07-01T15:00:00Z")
        self.assertIsNone(nrc.to_utc("07/01/2026", "10:00", "XYZ"))
        self.assertIsNone(nrc.to_utc("", "10:00", "ET"))


class EventReports(unittest.TestCase):
    def test_power_reactor_events_with_their_classes(self):
        ev = {e["number"]: e for e in report("events_20260224_rebuilt.html", "20260224")}
        hc, fermi = ev[58168], ev[58170]
        self.assertEqual((hc["type"], hc["facility"], hc["state"], hc["units"]), ("Power Reactor", "Hope Creek", "NJ", ["1"]))
        self.assertEqual((hc["class_code"], hc["level"], hc["emergency_class"]), ("unusual_event", 1, "Unusual Event"))
        self.assertEqual(hc["notified"], "2026-02-23T08:02:00Z")
        self.assertEqual(hc["event_time"], "2026-02-23T07:09:00Z")
        self.assertIn("Emergency Declared", hc["cfr"])
        self.assertEqual(hc["unit_info"][0]["scram_code"], "A/R")
        self.assertEqual((hc["unit_info"][0]["initial_power"], hc["unit_info"][0]["current_power"]), (100, 0))
        self.assertEqual(hc["headline"], "UNUSUAL EVENT - LOSS OF ALL OFFSITE POWER")
        self.assertTrue(hc["terminated"])
        self.assertFalse(hc["retracted"])
        self.assertEqual(hc["updates"], 1)
        self.assertTrue(hc["url"].endswith("/2026/20260224en#en58168"))
        self.assertEqual((fermi["level"], fermi["class_code"], fermi["terminated"]), (0, "non_emergency", False))

    def test_the_real_pages_parse(self):
        old = {e["number"]: e for e in report("events_20120109.html", "20120109")}
        self.assertEqual(set(old), {47580, 47581, 47578})
        pb = old[47581]
        self.assertEqual((pb["facility"], pb["units"], pb["region"], pb["state"]), ("PEACH BOTTOM", ["2", "3"], "1", "PA"))
        self.assertEqual(pb["emergency_class"], "Non Emergency")         # NON EMERGENCY in the old pages
        self.assertEqual(len(pb["unit_info"]), 2)
        fuel = old[47578]
        self.assertEqual((fuel["type"], fuel["state"], fuel["county"]), ("Fuel Cycle Facility", "TN", None))
        self.assertEqual(old[47580]["updates"], 2)
        new = {e["number"]: e for e in report("events_20260211.html", "20260211")}
        self.assertEqual(set(new), {58149, 58151, 58160})
        self.assertIsNone(new[58149]["county"])                            # a NUL byte on the NRC's page
        self.assertEqual(new[58160]["county"], "Bernalillo")

    def test_no_personal_names_are_kept(self):
        for name, ymd in (("events_20120109.html", "20120109"), ("events_20260211.html", "20260211"),
                          ("events_20260224_rebuilt.html", "20260224")):
            for e in report(name, ymd):
                self.assertFalse({"notified_by", "hq_ops_officer", "persons", "text"} & set(e))

    def test_index_links(self):
        dates = nrc.parse_index(text("index_2026_rebuilt.html"))
        self.assertEqual(dates[:3], ["20261125", "20261124", "20261123"])
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_classes(self):
        self.assertEqual(nrc.emergency_class("NON EMERGENCY")[:2], ("non_emergency", 0))
        self.assertEqual(nrc.emergency_class("Alert")[:2], ("alert", 2))
        self.assertEqual(nrc.emergency_class("Site Area Emergency")[:2], ("site_area_emergency", 3))
        self.assertEqual(nrc.emergency_class("General Emergency")[:2], ("general_emergency", 4))
        self.assertEqual(nrc.emergency_class("Notification of Unusual Event")[:2], ("unusual_event", 1))
        self.assertEqual(nrc.emergency_class("Something new"), (None, None, "Something new"))

    def test_headline_case(self):
        self.assertEqual(nrc.sentence("UNUSUAL EVENT - LOSS OF ALL OFFSITE POWER"), "Unusual Event - loss of all offsite power")
        self.assertEqual(nrc.sentence("HPCI DECLARED INOPERABLE"), "HPCI declared inoperable")
        self.assertEqual(nrc.sentence("Already mixed case"), "Already mixed case")


def pages(answers: dict):
    """A fetch that answers from a dict of URL -> body (bytes), or fails."""
    def fetch(url, timeout=40, *a):
        body = answers.get(url)
        return (body, None) if body is not None else (None, "HTTP 503")
    return fetch


class CollectEvents(unittest.TestCase):
    def index_and(self, *reports):
        idx = text("index_2026_rebuilt.html").encode()
        ans = {nrc.EVENTS_INDEX.format(year=2026): idx}
        for ymd, name in reports:
            ans[nrc.EVENTS_REPORT.format(year=2026, ymd=ymd)] = (FIX / name).read_bytes()
        return pages(ans)

    def test_reads_the_newest_reports_and_keeps_30_days(self):
        # The index lists Nov reports; the fixture page for 24 Feb stands in for the newest one.
        fetch = self.index_and(("20261125", "events_20260224_rebuilt.html"))
        now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        got, err = nrc.collect_events([], now, fetch)
        self.assertEqual(sorted(e["number"] for e in got), [58168, 58170])
        self.assertIn("report 20261124: HTTP 503", err)                   # a partial read: read
        self.assertTrue(cli.read_this_run(got, err, []))
        later = datetime(2026, 4, 1, tzinfo=timezone.utc)
        got2, _ = nrc.collect_events(got, later, self.index_and())
        self.assertEqual(got2, [])                                         # older than 30 days

    def test_a_failed_index_keeps_the_old_records_and_is_not_read(self):
        old = [{"number": 1, "notified": "2026-02-23T00:00:00Z", "report": "20260224"}]
        got, err = nrc.collect_events(old, NOW, pages({}))
        self.assertIs(got, old)
        self.assertTrue(err.startswith("every index failed"), err)
        self.assertFalse(cli.read_this_run(got, err, old))

    def test_every_report_failing_is_not_read(self):
        old = [{"number": 1, "notified": "2026-11-20T00:00:00Z", "report": "20261120"}]
        got, err = nrc.collect_events(old, datetime(2026, 11, 25, 12, tzinfo=timezone.utc), self.index_and())
        self.assertTrue(err.startswith("every report failed"), err)
        self.assertFalse(cli.read_this_run(got, err, old))

    def test_a_later_report_raising_the_class_is_marked(self):
        first = report("events_20260224_rebuilt.html", "20260224")
        low = [dict(e, level=0, class_code="non_emergency", emergency_class="Non Emergency", report="20260223")
               for e in first]
        fetch = self.index_and(("20261125", "events_20260224_rebuilt.html"))
        got, _ = nrc.collect_events(low, datetime(2026, 2, 25, tzinfo=timezone.utc), fetch)
        hc = next(e for e in got if e["number"] == 58168)
        self.assertEqual((hc["level"], hc["raised_at"]), (1, "2026-02-25T00:00:00Z"))


class CollectStatus(unittest.TestCase):
    def test_reads_the_start_of_the_year_file(self):
        body = (FIX / "PowerStatus_rebuilt.txt").read_bytes()
        calls = []

        def fetch(url, n, timeout=40):
            calls.append(url)
            return (body, False, None) if "2026PowerStatus" in url else (None, False, "HTTP 503")
        got, err = nrc.collect_status([], datetime(2026, 11, 25, 15, tzinfo=timezone.utc), fetch)
        self.assertIsNone(err)
        self.assertEqual([r["date"] for r in got], ["2026-11-25", "2026-11-24", "2026-11-23"])
        self.assertEqual(len(got[0]["units"]), 95)
        self.assertEqual(got[0]["units"]["Oconee 1"], 50)
        self.assertEqual(len(calls), 1)                                    # not January: last year's file not read

    def test_a_cut_read_drops_the_partial_line_and_the_oldest_date(self):
        t = text("PowerStatus_rebuilt.txt")
        cut = t[:len(t) - 20]                                              # ends mid-line on 23 Nov
        got = nrc.parse_status(cut, cut=True)
        self.assertEqual(sorted(got), ["2026-11-24", "2026-11-25"])
        self.assertEqual(len(got["2026-11-24"]), 95)

    def test_lf_and_crlf(self):
        t = text("PowerStatus_rebuilt.txt")
        self.assertEqual(nrc.parse_status(t), nrc.parse_status(t.replace("\r\n", "\n")))

    def test_a_failed_read_keeps_the_old_records(self):
        old = [{"date": "2026-11-24", "units": {"Cooper": 0}}]
        got, err = nrc.collect_status(old, datetime(2026, 11, 25, tzinfo=timezone.utc),
                                      lambda u, n, t=40: (None, False, "HTTP 503"))
        self.assertIs(got, old)
        self.assertFalse(cli.read_this_run(got, err, old))

    def test_in_january_last_years_file_fills_the_dates(self):
        jan = "ReportDt|Unit|Power\n01/02/2027 12:00:00 AM|Cooper|100\n01/01/2027 12:00:00 AM|Cooper|100\n"
        dec = "".join(f"12/{d:02d}/2026 12:00:00 AM|Cooper|{0 if d == 31 else 100}\n" for d in range(31, 0, -1))

        def fetch(url, n, timeout=40):
            return ((jan if "2027" in url else dec).encode(), False, None)
        got, err = nrc.collect_status([], datetime(2027, 1, 2, 15, tzinfo=timezone.utc), fetch)
        self.assertEqual(len(got), nrc.KEEP_DATES)
        self.assertEqual(got[0]["date"], "2027-01-02")
        self.assertEqual(got[2], {"date": "2026-12-31", "units": {"Cooper": 0}})


class Assess(unittest.TestCase):
    def test_a_shutdown_on_a_steady_unit_is_an_anomaly(self):
        recs = series({"Hope Creek 1": lambda i: 0 if i == 0 else 100, "Salem 1": lambda i: 100}, "2026-02-24")
        a = {x["unit"]: x for x in nrc.assess(recs, NOW)}
        self.assertNotIn("Salem 1", a)                                     # steady at 100%: no item
        hc = a["Hope Creek 1"]
        self.assertTrue(hc["shutdown"] and hc["anomaly"])
        self.assertEqual((hc["change"], hc["baseline_pairs"], hc["baseline_shutdowns"], hc["flag_rate"]), (-100, 29, 0, 0.0))

    def test_held_for_72_hours_while_still_at_zero(self):
        # The hold runs from the end of the report's day: 72 hours before NOW is 21 Feb 15:00 UTC.
        recs = series({"Hope Creek 1": lambda i: 0 if i <= 3 else 100}, "2026-02-24")
        self.assertTrue(nrc.assess(recs, NOW)[0]["anomaly"])               # 0% from 21 Feb, which ended 63 h ago
        recs = series({"Hope Creek 1": lambda i: 0 if i <= 4 else 100}, "2026-02-24")
        a = nrc.assess(recs, NOW)[0]
        self.assertTrue(a["shutdown"])
        self.assertFalse(a["anomaly"])                                     # 0% from 20 Feb: past the hold

    def test_a_unit_that_often_drops_is_not_flagged(self):
        # 0% every fifth day: shutdowns on more than 5% of its pairs
        recs = series({"Cycling 1": lambda i: 0 if i % 5 == 0 else 100}, "2026-02-24")
        a = nrc.assess(recs, NOW)[0]
        self.assertTrue(a["shutdown"])
        self.assertGreater(a["flag_rate"], nrc.FLAG_RATE_CAP)
        self.assertFalse(a["anomaly"])

    def test_a_short_baseline_is_not_flagged(self):
        recs = series({"New 1": lambda i: 0 if i == 0 else 100}, "2026-02-24", days=5)
        a = nrc.assess(recs, NOW)[0]
        self.assertTrue(a["shutdown"])
        self.assertFalse(a["anomaly"])

    def test_a_drop_from_low_power_is_not_a_shutdown(self):
        recs = series({"Low 1": lambda i: 0 if i == 0 else 10}, "2026-02-24")
        a = nrc.assess(recs, NOW)[0]
        self.assertFalse(a["shutdown"] or a["anomaly"])

    def test_the_rebuilt_days_have_no_shutdown(self):
        st = nrc.parse_status(text("PowerStatus_rebuilt.txt"))
        recs = [{"date": d, "units": st[d]} for d in sorted(st, reverse=True)]
        a = {x["unit"]: x for x in nrc.assess(recs, datetime(2026, 11, 25, 15, tzinfo=timezone.utc))}
        self.assertEqual(sorted(a), ["Brunswick 2", "Byron 1", "Callaway", "Cooper", "Millstone 3", "North Anna 2",
                                     "Oconee 1", "Palisades", "Point Beach 1", "River Bend Station 1", "Salem 1",
                                     "Waterford 3", "Watts Bar 2"])
        self.assertEqual((a["Oconee 1"]["power_before"], a["Oconee 1"]["power"]), (0, 50))
        self.assertEqual(a["Callaway"]["changed_on"], "2026-11-25")       # back to 100%: one item, that day
        self.assertFalse(any(x["anomaly"] or x["shutdown"] for x in a.values()))
        self.assertEqual(nrc.summary(recs), {"date": "2026-11-25", "units": 95, "full": 84, "below": 4, "zero": 7})


class Catalog(unittest.TestCase):
    def test_every_unit_on_the_status_report_is_placed(self):
        cat = nrc.catalog()["units"]
        units = nrc.parse_status(text("PowerStatus_rebuilt.txt"))["2026-11-25"]
        self.assertEqual([u for u in units if u not in cat], [])

    def test_units_lie_in_their_state_and_near_their_county(self):
        counties = json.loads((ROOT / "catalog" / "us_counties.json").read_text(encoding="utf-8"))["counties"]
        for name, (lat, lon, state, fips, _, _) in nrc.catalog()["units"].items():
            self.assertTrue(-125 < lon < -66 and 24 < lat < 50, name)
            self.assertIn(geo.country_at(lat, lon), ("US", None), name)    # None: a shore site off the 1:10m coast
            c = counties.get(fips)
            if c:                                                          # CT's counties left the Census file
                self.assertEqual(c[3], state, name)
                km = 6371 * math.hypot(math.radians(lat - c[0]), math.radians(lon - c[1]) * math.cos(math.radians(lat)))
                self.assertLess(km, 60, name)

    def test_event_facilities_match_units(self):
        for fac, units, st, want in (("Hope Creek", ["1"], "NJ", "Hope Creek 1"), ("PEACH BOTTOM", ["2", "3"], "PA", "Peach Bottom 2"),
                                     ("Fermi", ["2"], "MI", "Fermi 2"), ("St. Lucie", ["2"], "FL", "Saint Lucie 2"),
                                     ("River Bend", ["1"], "LA", "River Bend Station 1"), ("Callaway", ["1"], "MO", "Callaway"),
                                     ("Cook", ["1"], "MI", "D.C. Cook 1"), ("La Salle", ["2"], "IL", "LaSalle 2"),
                                     ("Columbia Generating Station", ["2"], "WA", "Columbia Generating Station"),
                                     ("Vogtle", [], "GA", "Vogtle 1")):
            self.assertEqual(nrc.place_unit(fac, units, st)[0], want, fac)
        self.assertEqual(nrc.place_unit("Hope Creek", ["1"], "PA"), (None, None))    # never across a state line
        self.assertEqual(nrc.place_unit("Nowhere", ["1"], "TX"), (None, None))


class FeedItems(unittest.TestCase):
    def setUp(self):
        self.regs = registers.ids(ROOT / "doctrine")
        self.events = (report("events_20260224_rebuilt.html", "20260224")
                       + report("events_20260211.html", "20260211") + report("events_20120109.html", "20120109"))
        self.status = series({"Hope Creek 1": lambda i: 0 if i == 0 else 100, "Salem 1": lambda i: 100,
                              "Oconee 1": lambda i: 50 if i < 5 else 100, "Fermi 2": lambda i: 0,
                              "Unknown 9": lambda i: 80}, "2026-02-24")

    def assertClean(self, fc):
        self.assertEqual(fc["dropped"], [])
        for x in fc["features"]:
            errs = [m for _, sev, m in contract.check(x, self.regs) if sev == "error"]
            self.assertEqual(errs, [], x["properties"]["id"])

    def test_events(self):
        fc = build(self.events)
        self.assertClean(fc)
        ev = items(fc, "nrc-event")
        # Power reactors and fuel facilities of the last 7 days only: not the Agreement State or research reactor reports
        self.assertEqual(set(ev), {"elements:nrc-event:58168", "elements:nrc-event:58170"})
        hc = ev["elements:nrc-event:58168"]
        p = hc["properties"]
        self.assertEqual(p["tier"], "anomaly")
        self.assertEqual(p["title"], "Unusual Event declared at Hope Creek 1 (NJ): Loss of all offsite power "
                                     "(NRC event 58168, since reported terminated)")
        self.assertEqual(p["baseline_ref"]["id"], "nrc-emergency-classes")
        self.assertEqual((p["signal"]["value"], p["signal"]["tail"]), (1, "high"))
        self.assertEqual((p["last_change"], p["last_change_at"]), ("new", "2026-02-23T08:02:00Z"))
        self.assertEqual(p["event_start"], "2026-02-23T07:09:00Z")
        self.assertEqual(hc["geometry"]["coordinates"], [-75.53778, 39.46672])
        self.assertEqual((p["precision_class"], p["subdivisions"], p["countries"]), ("point", ["US-NJ"], ["US"]))
        self.assertEqual(p["sea_areas"], [])                               # on the shore of Delaware Bay, on land
        self.assertEqual(p["measures"]["scram_units"], ["1"])
        self.assertEqual(p["sources"][0]["grade"], "B2")
        self.assertNotIn("response_stage", p)
        f = ev["elements:nrc-event:58170"]["properties"]
        self.assertEqual(f["tier"], "routine")
        self.assertIn("non-emergency report", f["title"])

    def test_the_hold_and_a_retraction(self):
        later = build(self.events, now=datetime(2026, 2, 26, 9, tzinfo=timezone.utc))   # 73 h after notification
        self.assertEqual(items(later, "nrc-event")["elements:nrc-event:58168"]["properties"]["tier"], "routine")
        gone = [dict(e, retracted=True) for e in self.events]
        p = items(build(gone), "nrc-event")["elements:nrc-event:58168"]["properties"]
        self.assertEqual(p["tier"], "routine")
        self.assertTrue(p["title"].endswith(", retracted"))

    def test_a_fuel_facility_without_a_county_is_placed_by_its_state(self):
        fuel = [dict(e, notified="2026-02-24T10:00:00Z") for e in report("events_20120109.html", "20120109")
                if e["number"] == 47578]
        fc = build(fuel)
        self.assertClean(fc)
        x = items(fc, "nrc-event")["elements:nrc-event:47578"]
        self.assertIsNone(x["geometry"])
        self.assertEqual((x["properties"]["precision_class"], x["properties"]["subdivisions"]), ("admin1", ["US-TN"]))
        self.assertEqual(x["properties"]["visual"]["type"], "page")

    def test_status(self):
        fc = build(status=self.status)
        self.assertClean(fc)
        st = items(fc, "nrc-reactor")
        self.assertEqual(set(st), {"elements:nrc-reactor:hope_creek_1", "elements:nrc-reactor:oconee_1",
                                   "elements:nrc-reactor:fermi_2", "elements:nrc-reactor:unknown_9",
                                   "elements:nrc-reactor:us"})
        hc = st["elements:nrc-reactor:hope_creek_1"]["properties"]
        self.assertEqual(hc["tier"], "anomaly")
        self.assertEqual(hc["title"], "Hope Creek 1: 0% power on 24 Feb 2026, down from 100% the report before (NRC daily status)")
        self.assertEqual((hc["data_as_of"], hc["data_as_of_precision"]), ("2026-02-24T00:00:00Z", "day"))
        self.assertEqual((hc["event_start"], hc["event_time_precision"]), ("2026-02-24T00:00:00Z", "day"))
        self.assertEqual((hc["last_change"], hc["last_change_at"]), ("changed", "2026-02-24T00:00:00Z"))
        self.assertEqual(hc["signal"]["value"], -100)
        self.assertEqual((hc["signal"]["baseline_n"], hc["signal"]["exceedance"]), (29, 1 / 30))
        self.assertEqual((hc["baseline_ref"]["type"], hc["baseline_ref"]["flag_rate"]), ("rolling", 0.0))
        for word in ("trip", "scram", "fault", "outage", "refuel", "because"):
            self.assertNotIn(word, hc["title"].lower())                    # no cause named
        fermi = st["elements:nrc-reactor:fermi_2"]["properties"]
        self.assertEqual(fermi["tier"], "routine")
        self.assertNotIn("signal", fermi)                                 # no change in the store
        self.assertIn("the same since at least 25 Jan 2026", fermi["title"])
        unknown = st["elements:nrc-reactor:unknown_9"]
        self.assertIsNone(unknown["geometry"])
        self.assertEqual(unknown["properties"]["precision_class"], "none")
        us = st["elements:nrc-reactor:us"]["properties"]
        self.assertEqual((us["precision_class"], us["signal"]["value"]), ("country", 2))

    def test_no_nrc_data_no_items(self):
        fc = build()
        self.assertEqual(items(fc, "nrc-event"), {})
        self.assertEqual(items(fc, "nrc-reactor"), {})

    def test_the_map_file(self):
        m = nrc.reactors_map(self.status)
        self.assertEqual(m["date"], "2026-02-24")
        hc = next(u for u in m["units"] if u["name"] == "Hope Creek 1")
        self.assertEqual((hc["power"], hc["previous"], hc["state"]), (0, 100, "NJ"))


class Lanes(unittest.TestCase):
    def test_the_lanes_have_health_keys(self):
        self.assertEqual(cli.LANES["nrc_events"], "nrc-events")
        self.assertEqual(cli.LANES["nrc_status"], "nrc-reactor-status")
        self.assertEqual(feed.SRC["nrc_events"]["id"], "nrc-events")
        self.assertEqual(feed.SRC["nrc_status"]["id"], "nrc-reactor-status")

    def test_the_registers_name_the_sources(self):
        src = json.loads((ROOT / "doctrine" / "sources.json").read_text(encoding="utf-8"))
        ids = {s["id"]: s for s in src["sources"]}
        for k in ("nrc-events", "nrc-reactor-status"):
            self.assertEqual(ids[k]["use"], "ingest")
            self.assertEqual(src["extra"][k]["grade"], "B2")
        for k in ("eurdep", "safecast", "iaea-pris", "iaea-iec", "epa-radnet"):
            self.assertNotEqual(ids[k]["use"], "ingest", k)


if __name__ == "__main__":
    unittest.main()
