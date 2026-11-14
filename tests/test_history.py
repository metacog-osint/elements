"""Offline tests for Elements' history (elements/history.py), the NWS catch-up (elements/weather.py) and the history
step of tools/elements.py. Fixtures in tests/fixtures/history/ are recorded data, trimmed, never invented: Elements'
own data commits and one response of NWS's alerts API (tests/make_history_fixtures.py, MANIFEST.json)."""
import gzip
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, history, weather  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "history"
LANES = ("usgs", "gdacs", "nhc", "cems", "firms", "usgs_volcano", "nws", "spc", "tsunami", "usdm", "meteoalarm", "emsc",
         "nifc")


def fx(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def data(health, **lanes):
    """Elements' data() shape: every lane, the given ones filled, fetched_at from that health record."""
    src = {"usgs": "usgs-earthquakes", "gdacs": "gdacs", "nhc": "nhc", "cems": "copernicus-ems", "firms": "nasa-firms",
           "usgs_volcano": "usgs-volcanoes", "nws": "nws-alerts", "spc": "spc-outlook", "tsunami": "noaa-tsunami",
           "usdm": "us-drought-monitor", "meteoalarm": "meteoalarm", "emsc": "emsc", "nifc": "nifc-wfigs"}
    return {k: {"records": lanes.get(k) or [], "fetched_at": (health.get(src[k]) or {}).get("last_ok")} for k in LANES} \
        | {"health": health}


def run(state, health, now, caught=None, **lanes):
    d = data(health, **lanes)
    return history.update(state, feed.build(d, now), health, now, caught)


class LeftTheFeed(unittest.TestCase):
    """A Severe Thunderstorm Warning (KABQ.SV.W.0428, 1 Nov) in one run and gone from the next."""

    def setUp(self):
        self.a, self.b = fx("nws_run_a.json"), fx("nws_run_b.json")
        self.s1, self.l1 = run({}, self.a["health"], t(self.a["committed_at"]), nws=self.a["nws"])
        self.s2, self.l2 = run(self.s1, self.b["health"], t(self.b["committed_at"]), nws=self.b["nws"])

    def test_first_run_logs_every_item_new(self):
        self.assertEqual({x["change"] for x in self.l1}, {"new"})
        self.assertEqual(len(self.l1), len(self.a["nws"]))
        self.assertTrue(all(x["format"] == "tic-history/1" and x["program"] == "elements" and x["lane"] == "nws-alerts"
                            for x in self.l1))

    def test_the_warning_that_left_is_ended_with_its_last_version(self):
        ended = [x for x in self.l2 if x["change"] == "ended"]
        self.assertEqual([x["id"] for x in ended], ["elements:nws:KABQ.SV.W.0428.2026"])
        x = ended[0]
        rec = next(r for r in self.a["nws"] if r["id"] == "KABQ.SV.W.0428.2026")
        self.assertEqual(x["item"]["properties"]["measures"]["vtec"], "KABQ.SV.W.0428.2026")
        self.assertEqual(x["first_seen"], "2026-11-01T23:50:24Z")
        self.assertEqual(x["last_seen"], "2026-11-01T23:50:24Z")
        self.assertEqual(x["end_reason"], "left the feed")
        # its own end time falls between the last sighting and the next run, so that is when it ended
        self.assertEqual(x["ended_at"], rec["ends"])
        self.assertLess(x["ended_at"], self.b["committed_at"])
        self.assertNotIn("elements:nws:KABQ.SV.W.0428.2026", self.s2["open"])

    def test_items_in_both_runs_stay_open_and_quiet(self):
        self.assertEqual({x["change"] for x in self.l2}, {"ended"})
        for r in self.b["nws"]:
            e = self.s2["open"][f"elements:nws:{r['id']}"]
            self.assertEqual(e["first_seen"], self.a["committed_at"])
            self.assertEqual(e["last_seen"], self.b["committed_at"])

    def test_an_end_time_already_past_at_the_last_sighting_gives_the_run_time(self):
        e = {"item": {"properties": {"valid_until": "2026-11-01T00:00:00Z"}}, "last_seen": "2026-11-01T23:50:24Z"}
        self.assertEqual(history.end_time(e, t("2026-11-02T06:42:24Z")), "2026-11-02T06:42:24Z")

    def test_published_at_and_accessed_at_are_not_changes(self):
        f = self.s1["open"]["elements:nws:KABQ.SV.W.0428.2026"]["item"]
        g = json.loads(json.dumps(f))
        g["properties"]["published_at"] = "2030-01-01T00:00:00Z"
        g["properties"]["sources"][0]["accessed_at"] = "2030-01-01T00:00:00Z"
        self.assertEqual(history.fingerprint(f), history.fingerprint(g))
        g["properties"]["title"] += " (updated)"
        self.assertNotEqual(history.fingerprint(f), history.fingerprint(g))


class FailedSource(unittest.TestCase):
    """NASA FIRMS failed on the run committed as c135e7f (12 Nov): its items must not end on that run."""

    def setUp(self):
        self.h = fx("health_firms_failed.json")
        self.item = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-98.5, 39.8]},
                     "properties": {"id": "elements:firms:US", "program": "elements", "tier": "routine",
                                    "sources": [{"id": "nasa-firms"}]}}
        self.state = {"open": {"elements:firms:US": {"lane": "nasa-firms", "first_seen": "2026-11-12T10:00:00Z",
                                                     "last_seen": "2026-11-12T16:36:09Z", "hash": "x", "updates": 0,
                                                     "peak_tier": "routine", "status": ["routine", None],
                                                     "item": self.item}}}

    def test_the_failed_run_reads_as_failed(self):
        self.assertNotIn("nasa-firms", history.lanes_ok(self.h["failed"]))
        self.assertIn("nasa-firms", history.lanes_ok(self.h["ok"]))

    def test_missing_items_of_a_failed_lane_stay_open(self):
        s, lines = history.update(self.state, {"features": []}, self.h["failed"], t("2026-11-12T17:18:38Z"))
        self.assertEqual(lines, [])
        self.assertIn("elements:firms:US", s["open"])

    def test_missing_items_of_a_lane_read_well_end(self):
        s, lines = history.update(self.state, {"features": []}, self.h["ok"], t("2026-11-12T18:00:00Z"))
        self.assertEqual([x["change"] for x in lines], ["ended"])
        self.assertNotIn("elements:firms:US", s["open"])

    def test_an_item_the_linter_dropped_is_not_ended(self):
        s, lines = history.update(self.state, {"features": [], "dropped": [{"id": "elements:firms:US", "errors": ["x"]}]},
                                  self.h["ok"], t("2026-11-12T18:00:00Z"))
        self.assertEqual(lines, [])


class AlertLevelMoved(unittest.TestCase):
    """Great Sitkin (332010) raised from ADVISORY to WATCH on 3 Nov: a changed line, and the peak tier kept."""

    def test_raised_level_is_a_changed_line(self):
        v = fx("volcano_raised.json")
        b, a = v["before"], v["after"]
        s1, _ = run({}, b["health"], t("2026-11-03T06:00:00Z"), usgs_volcano=b["records"])
        s2, lines = run(s1, a["health"], t("2026-11-03T07:10:38Z"), usgs_volcano=a["records"])
        ch = [x for x in lines if x["change"] == "changed"]
        self.assertEqual(len(ch), 1)
        self.assertEqual(ch[0]["was"]["response_stage"], "usgs_volcano:advisory")
        self.assertEqual(ch[0]["item"]["properties"]["response_stage"], "usgs_volcano:watch")
        self.assertEqual(s2["open"]["elements:usgs-volcano:332010"]["status"], ["anomaly", "usgs_volcano:watch"])


class CatchUp(unittest.TestCase):
    """NWS's alerts API, recorded about 01:45Z 14 Nov, against the active list of Elements' 01:36Z run."""

    def setUp(self):
        self.m = fx("MANIFEST.json")["catchup"]
        self.since = (FIX / "nws_since.json").read_bytes()
        self.active = fx("nws_active_d98bd52.json")["records"]

    def fetch_pages(self, pages):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return (pages[len(calls) - 1] if len(calls) <= len(pages) else None), None
        return fetch, calls

    def test_the_query_and_its_pagination(self):
        empty = json.dumps({"features": [], "pagination": {"next": "https://api.weather.gov/alerts?cursor=z"}}).encode()
        fetch, calls = self.fetch_pages([self.since, empty])
        recs, err = weather.collect_nws_since("2026-11-13T00:00:00Z", fetch)
        self.assertIsNone(err)
        self.assertIn("start=2026-11-13T00:00:00Z", calls[0])
        self.assertIn("severity=Severe,Extreme", calls[0])
        self.assertEqual(calls[1], json.loads(self.since)["pagination"]["next"])
        self.assertEqual(len(calls), 2)           # an empty page stops it
        self.assertEqual(sorted(r["id"] for r in recs), sorted(self.m["not_active"] + self.m["active"]))

    def test_a_failed_fetch_gives_nothing_and_says_so(self):
        recs, err = weather.collect_nws_since("2026-11-13T00:00:00Z", lambda u, t_: (None, "HTTP 503"))
        self.assertEqual((recs, err), ([], "HTTP 503"))

    def test_a_failed_later_page_keeps_what_was_read(self):
        recs, err = weather.collect_nws_since("2026-11-13T00:00:00Z", self.fetch_pages([self.since])[0])
        self.assertEqual(len(recs), 5)
        self.assertTrue(err.startswith("partial: page 2"))

    def caught(self, now):
        empty = json.dumps({"features": []}).encode()
        recs, _ = weather.collect_nws_since("2026-11-13T00:00:00Z", self.fetch_pages([self.since, empty])[0])
        act = {r["id"] for r in self.active}
        gone = [r for r in recs if r["id"] not in act]
        return feed._weather_items({"nws": {"records": gone, "fetched_at": "2026-11-14T01:45:00Z"}}, now)

    def test_alerts_no_longer_active_are_logged_new_and_ended(self):
        now = t("2026-11-14T01:45:00Z")
        health = {"nws-alerts": {"last_ok": "2026-11-14T01:45:00Z", "checked_at": "2026-11-14T01:45:00Z"}}
        s, lines = run({}, health, now, caught=self.caught(now), nws=self.active)
        live = {f"elements:nws:{i}" for i in self.m["active"]}
        gone = {f"elements:nws:{i}" for i in self.m["not_active"]}
        self.assertEqual({x["id"] for x in lines if x["change"] == "new" and x.get("seen_live") is None}, live)
        caught = [x for x in lines if x.get("seen_live") is False]
        self.assertEqual({x["id"] for x in caught}, gone)
        self.assertEqual(sorted(x["change"] for x in caught), sorted(["new", "ended"] * len(gone)))
        for x in caught:
            if x["change"] == "ended":
                self.assertEqual(x["end_reason"], "issued and ended between runs")
                self.assertLessEqual(x["ended_at"], "2026-11-14T01:45:00Z")
        self.assertEqual(set(s["recently_ended"]), gone)
        # the next run does not log them again
        s2, lines2 = run(s, health, now + timedelta(hours=1), caught=self.caught(now + timedelta(hours=1)), nws=self.active)
        self.assertEqual(lines2, [])

    def test_start_time_rules(self):
        now = t("2026-11-14T02:00:00Z")
        self.assertEqual(weather.catchup_start("2026-11-14T01:36:00Z", now), "2026-11-14T00:36:00Z")
        self.assertEqual(weather.catchup_start(None, now), "2026-11-11T02:00:00Z")              # 72 h at most
        self.assertEqual(weather.catchup_start("2026-11-01T00:00:00Z", now), "2026-11-11T02:00:00Z")
        self.assertEqual(weather.catchup_start("2026-11-14T01:59:00Z", now), "2026-11-14T00:59:00Z")


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        a, b = fx("nws_run_a.json"), fx("nws_run_b.json")
        s1, l1 = run({}, a["health"], t(a["committed_at"]), nws=a["nws"])
        self.s2, l2 = run(s1, b["health"], t(b["committed_at"]), nws=b["nws"])
        history.append_log(self.dir, l1)
        history.append_log(self.dir, l2)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_one_file_per_day_then_gzipped_once_and_the_same_bytes_anywhere(self):
        self.assertTrue((self.dir / "log/2026/11/01.jsonl").exists())
        self.assertTrue((self.dir / "log/2026/11/02.jsonl").exists())
        plain = (self.dir / "log/2026/11/01.jsonl").read_bytes()
        self.assertEqual(history.close_days(self.dir, "2026-11-02"), ["2026-11-01"])
        gz = (self.dir / "log/2026/11/01.jsonl.gz").read_bytes()
        self.assertEqual(gzip.decompress(gz), plain)
        self.assertFalse((self.dir / "log/2026/11/01.jsonl").exists())
        other = Path(tempfile.mkdtemp())
        try:
            (other / "log/2026/11").mkdir(parents=True)
            (other / "log/2026/11/01.jsonl").write_bytes(plain)
            history.close_days(other, "2026-11-02")
            self.assertEqual((other / "log/2026/11/01.jsonl.gz").read_bytes(), gz)
        finally:
            shutil.rmtree(other)
        self.assertTrue((self.dir / "log/2026/11/02.jsonl").exists())     # today stays open

    def test_read_days_reads_plain_and_gzipped(self):
        history.close_days(self.dir, "2026-11-02")
        lines = history.read_days(self.dir, "2026-11-01", "2026-11-02")
        self.assertEqual([x["change"] for x in lines].count("ended"), 1)
        self.assertEqual(len(lines), 4)

    def test_state_round_trip_one_item_per_line(self):
        history.save_state(self.dir, self.s2)
        text = (self.dir / "state.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(text), json.loads(json.dumps(self.s2)))
        self.assertEqual(text.count("\n"), len(self.s2["open"]) + 2)

    def test_ended_file_lists_recent_ends_not_open_again(self):
        now = t("2026-11-02T07:00:00Z")
        fc = history.ended_collection(self.dir, self.s2, now)
        self.assertEqual([f["properties"]["id"] for f in fc["features"]], ["elements:nws:KABQ.SV.W.0428.2026"])
        h = fc["features"][0]["history"]
        self.assertEqual(h["end_reason"], "left the feed")
        self.assertEqual(h["first_seen"], "2026-11-01T23:50:24Z")
        self.assertNotIn("history", fc["features"][0]["properties"])
        self.assertEqual(history.ended_collection(self.dir, self.s2, now + timedelta(days=8))["features"], [])
        reopened = {"open": {"elements:nws:KABQ.SV.W.0428.2026": {}}}
        self.assertEqual(history.ended_collection(self.dir, reopened, now)["features"], [])


class Workflow(unittest.TestCase):
    def test_history_runs_after_collect_and_is_committed_without_starting_a_run(self):
        wf = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn('paths-ignore: ["data/**", "history/**"]', wf)
        self.assertLess(wf.index("tools/elements.py collect"), wf.index("tools/elements.py history"))
        self.assertLess(wf.index("tools/elements.py history"), wf.index("git add data history"))
        self.assertLess(wf.index("git add data history"), wf.index("tools/elements.py build"))
        self.assertIn("data/nws_recent.json", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_history.py", ci)


if __name__ == "__main__":
    unittest.main()
