"""The record-only lanes (ideas#233): NWS Moderate/Minor, green GDACS wildfires, low-confidence FIRMS cells."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elements import firms, firms_store, wider  # noqa: E402

NOW = datetime(2026, 11, 24, 2, 5, tzinfo=timezone.utc)
OID = "urn:oid:2.49.0.1.840.0."


def alert(n, severity="Minor"):
    return {"geometry": None, "properties": {
        "id": f"{OID}abc{n}.001.1", "@id": f"https://api.weather.gov/alerts/{OID}abc{n}.001.1", "severity": severity,
        "sent": "2026-11-24T01:00:00+00:00", "expires": "2026-11-24T09:00:00+00:00", "messageType": "Alert",
        "event": "Frost Advisory", "senderName": "NWS Test", "headline": "h", "areaDesc": "A; B",
        "geocode": {"UGC": ["MNZ001"]}, "parameters": {"VTEC": []}, "references": [], "description": "long text"}}


def gdacs(n, to="2026-11-23T00:00:00", alert_level="Green"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [20.0, 10.0]}, "properties": {
        "eventtype": "WF", "eventid": n, "episodeid": 1, "name": f"Fire {n}", "alertlevel": alert_level,
        "episodealertlevel": alert_level, "alertscore": 0, "fromdate": "2026-11-20T00:00:00", "todate": to,
        "iscurrent": "true", "country": "Chad", "severitydata": {"severity": 10, "severityunit": "ha"}, "url": {}}}


def pages(*docs):
    answers = [json.dumps(d).encode() if d is not None else b"" for d in docs]
    calls = []

    def fetch(url, timeout, *a):
        calls.append(url)
        return answers.pop(0) if answers else b"", None
    fetch.calls = calls
    return fetch


class Nws(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_keeps_moderate_minor_once_without_description(self):
        doc = {"features": [alert(1), alert(2, "Moderate"), alert(3, "Severe")]}
        self.assertIn("2 new", wider.update_nws(self.root, NOW, pages(doc)))
        self.assertIn("0 new", wider.update_nws(self.root, NOW + timedelta(hours=1), pages(doc)))
        rows = wider._recent(self.root, NOW, 2)
        self.assertEqual(sorted(x["severity"] for x in rows), ["Minor", "Moderate"])
        self.assertNotIn("description", rows[0])

    def test_partial_read_keeps_start(self):
        def fetch(url, timeout, *a):
            if "page2" in url:
                return None, "HTTP 503"
            return json.dumps({"features": [alert(1)], "pagination": {"next": "https://x/page2"}}).encode(), None
        self.assertIn("partial", wider.update_nws(self.root, NOW, fetch))
        self.assertFalse((self.root / "state.json").exists())
        self.assertEqual(len(wider._recent(self.root, NOW, 2)), 1)

    def test_start_is_an_hour_before_last_complete_and_capped(self):
        wider.update_nws(self.root, NOW, pages({"features": []}))
        self.assertEqual(wider.nws_start(self.root, NOW + timedelta(hours=1)), "2026-11-24T01:05:00Z")
        self.assertEqual(wider.nws_start(self.root, NOW + timedelta(days=9)), "2026-11-30T02:05:00Z")


class Gdacs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_every_page_and_logs_changes_only(self):
        first = {"features": [gdacs(i) for i in range(100)]}
        second = {"features": [gdacs(100), gdacs(101, alert_level="Orange")]}
        fetch = pages(first, second)
        self.assertIn("101 new or changed of 101", wider.update_gdacs(self.root, NOW, fetch))
        self.assertIn("pagenumber=2", fetch.calls[1])
        later = NOW + timedelta(hours=1)
        self.assertIn("0 new", wider.update_gdacs(self.root, later, pages({"features": [gdacs(5)]})))
        moved = {"features": [gdacs(5, to="2026-11-24T00:00:00")]}
        self.assertIn("1 new", wider.update_gdacs(self.root, later, pages(moved)))
        self.assertEqual([x["change"] for x in wider._recent(self.root, NOW, 2) if x["id"] == "WF-5"], ["new", "changed"])

    def test_empty_body_ends_the_read(self):
        self.assertIn("0 new or changed of 0", wider.update_gdacs(self.root, NOW, pages(None)))

    def test_one_lane_failing_leaves_the_other(self):
        def fetch(url, timeout, *a):
            if "weather.gov" in url:
                raise RuntimeError("boom")
            return json.dumps({"features": [gdacs(1)]}).encode(), None
        out = wider.update_all(self.root, NOW, fetch)
        self.assertIn("failed", out[0])
        self.assertIn("1 new", out[1])


class FirmsLow(unittest.TestCase):
    CSV = (b"latitude,longitude,acq_date,acq_time,confidence,frp\n"
           b"10.1,20.1,2026-11-24,0100,n,5\n10.2,20.2,2026-11-24,0100,h,6\n"
           b"11.1,21.1,2026-11-24,0100,l,1\n12.1,22.1,2026-11-24,0100,low,2\n")

    def test_low_is_kept_apart(self):
        kept, low = firms.parse_split(self.CSV)
        self.assertEqual((len(kept), len(low)), (2, 2))
        self.assertEqual(len(firms.parse(self.CSV)), 2)

    def test_low_goes_to_its_own_asset_and_not_the_main_cells(self):
        kept, low = firms.parse_split(self.CSV)
        payload = firms.aggregate(kept, NOW)
        payload["low"] = {k: v for k, v in firms.aggregate(low, NOW).items() if k != "daily"}
        self.assertNotIn("low", firms_store.snapshot(payload))
        snap = firms_store.low_snapshot(payload)
        self.assertEqual((snap["format"], snap["detections"]), (firms_store.LOW_FORMAT, 2))
        self.assertEqual(firms_store.low_asset_name(NOW), "firms-low-cells-20261124T02Z.json.gz")
        self.assertIsNone(firms_store.low_snapshot({"low": {"cells": []}}))


if __name__ == "__main__":
    unittest.main()
