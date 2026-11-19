"""A source counts as read only when this run read it (15 Nov 2026).

When a source fails, Elements keeps its last good records in data/, so its items stay in the feed. data/health.json
used to call that source read whenever records were left, which made the history step, and COP's ledger reading the
feed's health block, take the kept items as seen again on every failed run. Now a kept copy is "not read": its items
neither end nor count as sightings, and a partial read (some of a source's parts answered) still counts as read.
"""
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, firms, history, meteoalarm, tsunami  # noqa: E402

_spec = importlib.util.spec_from_file_location("elements_cli", ROOT / "tools" / "elements.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

NOW = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)


def down(*a, **k):
    return None, "HTTP 503"


class ReadThisRun(unittest.TestCase):
    def test_no_error_is_read(self):
        self.assertTrue(cli.read_this_run([], None, [{"id": "a"}]))      # read, and nothing is happening

    def test_the_previous_records_handed_back_are_not_read(self):
        prev = [{"id": "a"}]
        self.assertFalse(cli.read_this_run(prev, "HTTP 503", prev))
        self.assertFalse(cli.read_this_run([], "HTTP 503", prev))

    def test_a_partial_read_is_read(self):
        self.assertTrue(cli.read_this_run([{"id": "b"}], "1 of 3 countries failed: spain: HTTP 503", [{"id": "a"}]))

    def test_every_part_failing_is_not_read(self):
        self.assertFalse(cli.read_this_run([{"id": "a2"}], "every country failed: spain: HTTP 503", [{"id": "a"}]))
        self.assertFalse(cli.read_this_run([{"id": "a2"}], "every centre failed: NTWC feed: HTTP 503", [{"id": "a"}]))


class Collectors(unittest.TestCase):
    """What each collector hands back when nothing answered, so read_this_run can tell."""

    def test_firms_keeps_the_same_payload(self):
        old = {"cells": [[1]], "detections": 1}
        got, err = firms.collect_firms(old, NOW, down)
        self.assertIs(got, old)
        self.assertFalse(cli.read_this_run(got, err, old))

    def test_meteoalarm_with_only_kept_warnings_says_every_country_failed(self):
        old = [{"id": "x", "feed": "spain", "expires": "2026-11-16T00:00:00Z", "level": 2, "country": "ES",
                "onset": None}]
        got, err = meteoalarm.collect(old, NOW, down, feeds=["spain", "france"])
        self.assertEqual([r["id"] for r in got], ["x"])
        self.assertTrue(err.startswith("every country failed"), err)
        self.assertFalse(cli.read_this_run(got, err, old))

    def test_tsunami_with_no_centre_answering_says_so(self):
        old = [{"id": "t", "sent": "2026-11-15T10:00:00Z"}]
        got, err = tsunami.collect(old, NOW, down)
        self.assertEqual([r["id"] for r in got], ["t"])
        self.assertTrue(err.startswith("every centre failed"), err)
        self.assertFalse(cli.read_this_run(got, err, old))


class FeedBlock(unittest.TestCase):
    def test_the_feed_carries_the_health_block_keyed_by_source_id(self):
        h = {src: {"last_ok": "2026-11-15T17:00:00Z", "checked_at": "2026-11-15T17:00:00Z", "failures": 0}
             for src in cli.LANES.values()}
        h["nasa-firms"] = {"last_ok": "2026-11-15T11:00:00Z", "checked_at": "2026-11-15T17:00:00Z", "failures": 2}
        d = {k: {"records": [], "fetched_at": "2026-11-15T17:00:00Z"} for k in cli.LANES} | {"health": h}
        doc = feed.build(d, NOW)
        # The record as kept, plus revision 2.1's state per lane (19 Nov 2026); data/health.json is left as it was.
        self.assertEqual(set(doc["health"]), set(h))
        for k, e in h.items():
            self.assertEqual({x: doc["health"][k][x] for x in e}, e)
        self.assertEqual(doc["health"]["nasa-firms"]["state"], "failing")
        self.assertNotIn("state", h["nasa-firms"])
        self.assertEqual(history.lanes_ok(doc["health"]), set(cli.LANES.values()) - {"nasa-firms"})

    def test_every_live_item_source_has_a_health_key(self):
        # The sources the published feed's items carried on 15 Nov 2026 (COP's snapshot, 20:24 UTC).
        seen = {"usgs-earthquakes", "emsc", "gdacs", "copernicus-ems", "usgs-volcanoes", "nws-alerts", "spc-outlook",
                "noaa-tsunami", "us-drought-monitor", "meteoalarm", "nifc-wfigs", "nasa-firms"}
        self.assertTrue(seen <= set(cli.LANES.values()), seen - set(cli.LANES.values()))


if __name__ == "__main__":
    unittest.main()
