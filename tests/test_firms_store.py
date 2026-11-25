"""Offline tests for the hourly FIRMS cell store (no network; `gh` is replaced by a fake)."""
import gzip
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elements import firms, firms_store  # noqa: E402

NOW = datetime(2026, 11, 24, 1, 5, 30, tzinfo=timezone.utc)


def payload(end=NOW):
    dets = [(10.1, 20.1, end - timedelta(hours=2), True, 5.0), (10.2, 20.2, end - timedelta(hours=30), False, 1.0)]
    return firms.aggregate(dets, end) | {"via": {"VIIRS_NOAA20_NRT": "api"}, "key_status": {"current_transactions": 1}}


class FakeGh:
    def __init__(self, assets=None, view_error=None):
        self.assets, self.view_error, self.calls = assets, view_error, []

    def __call__(self, cmd, **_):
        args = cmd[1:]
        self.calls.append(args)
        if args[:2] == ["release", "view"]:
            if self.view_error:
                return SimpleNamespace(returncode=1, stdout="", stderr=self.view_error)
            if self.assets is None:
                return SimpleNamespace(returncode=1, stdout="", stderr="release not found")
            return SimpleNamespace(returncode=0, stdout="\n".join(self.assets), stderr="")
        if args[:2] == ["release", "create"]:
            self.assets = []
        if args[:2] == ["release", "upload"]:
            self.assets.append(Path(args[3]).name)
        return SimpleNamespace(returncode=0, stdout="", stderr="")


class Store(unittest.TestCase):
    def test_names_and_month(self):
        self.assertEqual(firms_store.release_tag(NOW), "firms-cells-2026-11")
        self.assertEqual(firms_store.asset_name(NOW), "firms-cells-20261124T01Z.json.gz")

    def test_snapshot_leaves_out_key_counts_and_is_stable(self):
        s = firms_store.snapshot(payload())
        self.assertNotIn("key_status", s)
        self.assertNotIn("daily", s)
        self.assertFalse(s["backfilled"])
        self.assertEqual(firms_store.encode(s), firms_store.encode(s))
        self.assertEqual(json.loads(gzip.decompress(firms_store.encode(s)))["detections"], 1)

    def test_first_run_creates_release_and_uploads(self):
        gh = FakeGh()
        with tempfile.TemporaryDirectory() as d:
            line = firms_store.store_run(payload(), Path(d), NOW + timedelta(minutes=1), gh)
        self.assertIn("stored", line)
        self.assertEqual(gh.assets, ["firms-cells-20261124T01Z.json.gz"])
        self.assertTrue(any(c[:2] == ["release", "create"] and "--latest=false" in c for c in gh.calls))

    def test_hour_already_stored_is_never_replaced(self):
        gh = FakeGh(["firms-cells-20261124T01Z.json.gz"])
        with tempfile.TemporaryDirectory() as d:
            line = firms_store.store_run(payload(), Path(d), NOW + timedelta(minutes=1), gh)
        self.assertIn("already there", line)
        self.assertFalse(any(c[:2] == ["release", "upload"] for c in gh.calls))
        self.assertFalse(any("--clobber" in c for c in gh.calls))

    def test_kept_copy_and_empty_store_nothing(self):
        gh = FakeGh()
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("kept copy", firms_store.store_run(payload(), Path(d), NOW + timedelta(hours=3), gh))
            self.assertIn("no cells", firms_store.store_run({}, Path(d), NOW, gh))
        self.assertEqual(gh.calls, [])

    def test_github_unreadable_uploads_nothing(self):
        gh = FakeGh(view_error="HTTP 502")
        with tempfile.TemporaryDirectory() as d, self.assertRaises(RuntimeError):
            firms_store.store_run(payload(), Path(d), NOW, gh)
        self.assertFalse(any(c[:2] == ["release", "upload"] for c in gh.calls))

    def test_rebuilt_hour_is_marked_and_windowed(self):
        end = datetime(2026, 11, 20, 6, tzinfo=timezone.utc)
        dets = [(10.1, 20.1, end - timedelta(hours=1), True, 5.0), (10.1, 20.1, end - timedelta(hours=25), True, 5.0),
                (10.1, 20.1, end + timedelta(hours=1), True, 5.0)]
        s = firms_store.rebuild_hour(dets, end, {"x": "public 7-day file"}, "note")
        self.assertTrue(s["backfilled"])
        self.assertEqual(s["detections"], 1)
        self.assertEqual(s["note"], "note")


if __name__ == "__main__":
    unittest.main()
