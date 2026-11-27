"""Tests for tools/tic_archive.py (the private archive uploader). Runs against a local DirStore, never GitHub."""
import gzip
import json
import os
import sys
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
for cand in (HERE, HERE.parent / "tools", HERE.parent):
    if (cand / "tic_archive.py").exists():
        sys.path.insert(0, str(cand))
        break
import tic_archive as ta  # noqa: E402

T0 = datetime(2026, 11, 19, 6, 0, 0, tzinfo=timezone.utc)


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.src = root / "src"
        self.src.mkdir()
        self.store = ta.DirStore(root / "store")
        self.arch = ta.Archive(self.store, "testprog", "raw")

    def tearDown(self):
        self.td.cleanup()

    def write(self, rel, data):
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def put(self, now=T0, **kw):
        return self.arch.put(self.src, now=now, **kw)

    def restored(self, snapshot=None):
        dest = Path(self.td.name) / f"restore-{len(os.listdir(self.td.name))}"
        self.arch.restore(dest, snapshot)
        return {p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob("*") if p.is_file()}


class PutTests(Base):
    def test_first_put_uploads_tar_and_index_to_month_release(self):
        self.write("a/1.json", "one")
        self.write("b/2.xml", "two")
        r = self.put()
        self.assertEqual(r["status"], "uploaded")
        self.assertEqual(r["tag"], "testprog-raw-2026-11")
        names = sorted(self.store.assets("testprog-raw-2026-11"))
        self.assertEqual(len(names), 2)
        self.assertTrue(all(n.startswith("20261119T060000Z-") for n in names))
        self.assertEqual(sorted(n.split(".", 1)[1] for n in names), ["files.json", "tar.gz"])
        self.assertEqual(self.restored(), {"a/1.json": b"one", "b/2.xml": b"two"})

    def test_unchanged_snapshot_uploads_nothing(self):
        self.write("a.txt", "x")
        self.put()
        r = self.put(now=T0 + timedelta(hours=6))
        self.assertEqual(r["status"], "unchanged")
        self.assertEqual(len(self.store.assets("testprog-raw-2026-11")), 2)

    def test_second_put_uploads_only_new_content_and_index_lists_all(self):
        self.write("a.txt", "x")
        self.put()
        self.write("b.txt", "y")
        r = self.put(now=T0 + timedelta(hours=6))
        self.assertEqual(r["doc"]["new_files"], 1)
        self.assertEqual(r["doc"]["file_count"], 2)
        tar = [n for n in r["assets"] if n.endswith(".tar.gz")][0]
        with tarfile.open(self.store.root / r["tag"] / tar) as t:
            self.assertEqual(len(t.getmembers()), 1)
        self.assertEqual(self.restored(), {"a.txt": b"x", "b.txt": b"y"})

    def test_every_snapshot_restorable_after_files_change_or_vanish(self):
        self.write("a.txt", "v1")
        first = self.put()
        self.write("a.txt", "v2")
        (self.src / "a.txt").unlink()
        self.write("c.txt", "z")
        self.put(now=T0 + timedelta(hours=6))
        idx1 = [n for n in first["assets"] if n.endswith(".files.json")][0]
        self.assertEqual(self.restored(idx1), {"a.txt": b"v1"})
        self.assertEqual(self.restored(), {"c.txt": b"z"})

    def test_append_only_nothing_replaced(self):
        self.write("log.jsonl", "1\n")
        self.put()
        before = {n: (self.store.root / "testprog-raw-2026-11" / n).read_bytes()
                  for n in self.store.assets("testprog-raw-2026-11")}
        self.write("log.jsonl", "1\n2\n")
        self.put(now=T0 + timedelta(hours=1))
        after = self.store.assets("testprog-raw-2026-11")
        self.assertEqual(len(after), 4)
        for n, data in before.items():
            self.assertEqual((self.store.root / "testprog-raw-2026-11" / n).read_bytes(), data)

    def test_new_month_new_release_reuses_earlier_assets(self):
        self.write("a.txt", "x")
        self.put()
        self.write("b.txt", "y")
        r = self.put(now=datetime(2026, 12, 1, 0, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(r["tag"], "testprog-raw-2026-12")
        self.assertEqual(r["doc"]["new_files"], 1)
        self.assertEqual(self.restored(), {"a.txt": b"x", "b.txt": b"y"})

    def test_tar_is_deterministic(self):
        self.write("a.txt", "x")
        self.write("d/b.txt", "y")
        r1 = self.put()
        other = ta.Archive(ta.DirStore(Path(self.td.name) / "store2"), "testprog", "raw")
        r2 = other.put(self.src, now=T0)
        t1 = [n for n in r1["assets"] if n.endswith(".tar.gz")]
        t2 = [n for n in r2["assets"] if n.endswith(".tar.gz")]
        self.assertEqual(t1, t2)

    def test_duplicate_content_stored_once(self):
        self.write("a.txt", "same")
        self.write("b.txt", "same")
        r = self.put()
        self.assertEqual(r["doc"]["new_files"], 1)
        self.assertEqual(self.restored(), {"a.txt": b"same", "b.txt": b"same"})

    def test_include_and_exclude(self):
        self.write("meta-network/x.md", "indicator")
        self.write("dfrlab-rss/y.xml", "reporter text")
        self.write("meta-readme/z.md", "table")
        self.write("index.jsonl", "{}")
        self.put(exclude=["meta-network/*", "dfrlab-rss/*"])
        self.assertEqual(sorted(self.restored()), ["index.jsonl", "meta-readme/z.md"])

    def test_several_named_sources(self):
        other = Path(self.td.name) / "other"
        (other / "x").mkdir(parents=True)
        (other / "x" / "o.txt").write_bytes(b"o")
        self.write("a.txt", "a")
        self.arch.put([("one", self.src), ("two", other)], now=T0)
        self.assertEqual(self.restored(), {"one/a.txt": b"a", "two/x/o.txt": b"o"})
        with self.assertRaises(ta.ArchiveError):
            self.arch.put([str(self.src), str(other)], now=T0)        # unnamed
        with self.assertRaises(ta.ArchiveError):
            self.arch.put([("one", self.src), ("one", other)], now=T0)  # duplicate name

    def test_missing_or_empty_source_fails(self):
        with self.assertRaises(ta.ArchiveError):
            self.arch.put(Path(self.td.name) / "nope", now=T0)
        with self.assertRaises(ta.ArchiveError):
            self.put()

    def test_dry_run_uploads_nothing(self):
        self.write("a.txt", "x")
        r = self.put(dry_run=True)
        self.assertEqual(r["status"], "dry-run")
        self.assertEqual(self.store.tags("testprog-"), [])

    def test_min_interval(self):
        self.write("a.txt", "x")
        self.put()
        self.write("a.txt", "y")
        self.assertEqual(self.put(now=T0 + timedelta(days=2), min_interval_hours=24 * 7)["status"], "too-soon")
        self.assertEqual(self.put(now=T0 + timedelta(days=8), min_interval_hours=24 * 7)["status"], "uploaded")

    def test_rollover_before_asset_limit(self):
        self.store.create("testprog-raw-2026-11")
        d = self.store.root / "testprog-raw-2026-11"
        for i in range(ta.ASSET_LIMIT - ta.ASSET_MARGIN - 1):
            (d / f"filler-{i}.bin").write_bytes(b"")
        self.write("a.txt", "x")
        r = self.put()
        self.assertEqual(r["tag"], "testprog-raw-2026-11.2")
        self.write("b.txt", "y")
        r = self.put(now=T0 + timedelta(hours=1))
        self.assertEqual(r["tag"], "testprog-raw-2026-11.2")
        self.assertEqual(self.restored(), {"a.txt": b"x", "b.txt": b"y"})

    def test_large_input_split_into_several_tars(self):
        for i in range(5):
            self.write(f"f{i}.bin", os.urandom(1000))
        r = self.put(max_tar_input=2500)
        self.assertEqual(sum(1 for n in r["assets"] if n.endswith(".tar.gz")), 3)
        self.assertEqual(len(self.restored()), 5)

    def test_existing_asset_name_never_clobbered(self):
        self.write("a.txt", "x")
        r = self.put()
        tar = [n for n in r["assets"] if n.endswith(".tar.gz")][0]
        with self.assertRaises(ta.ArchiveError):
            self.store.upload(r["tag"], [self.store.root / r["tag"] / tar])

    def test_bad_names_refused(self):
        with self.assertRaises(ta.ArchiveError):
            ta.Archive(self.store, "Orbit", "raw")
        with self.assertRaises(ta.ArchiveError):
            ta.Archive(self.store, "orbit", "raw/x")


class RedactTests(Base):
    def test_env_value_and_param_removed_from_plain_and_gz(self):
        os.environ["TA_TEST_APPNAME"] = "secret-app-name"
        try:
            red = ta.Redactor(["TA_TEST_APPNAME"], ["appname"])
            self.write("rw/1.json", '{"href":"https://api.reliefweb.int/v1/x?appname=secret-app-name&limit=1"}')
            self.write("rw/2.json.gz", gzip.compress(b'{"links":{"self":"...?appname=other-value"}, "n": "secret-app-name"}'))
            self.put(redactor=red)
        finally:
            del os.environ["TA_TEST_APPNAME"]
        out = self.restored()
        plain = out["rw/1.json"]
        inner = gzip.decompress(out["rw/2.json.gz"])
        for blob in (plain, inner):
            self.assertNotIn(b"secret-app-name", blob)
            self.assertNotIn(b"other-value", blob)
            self.assertIn(b"REDACTED", blob)
        self.assertIn(b"limit=1", plain)

    def test_missing_env_value_refuses(self):
        os.environ.pop("TA_TEST_UNSET", None)
        with self.assertRaises(ta.ArchiveError):
            ta.Redactor(["TA_TEST_UNSET"], [])

    def test_source_files_not_modified(self):
        os.environ["TA_TEST_APPNAME"] = "abc123def"
        try:
            p = self.write("x.json", "?appname=abc123def")
            self.put(redactor=ta.Redactor(["TA_TEST_APPNAME"], []))
        finally:
            del os.environ["TA_TEST_APPNAME"]
        self.assertEqual(p.read_bytes(), b"?appname=abc123def")

    def test_redacted_files_marked_in_index(self):
        os.environ["TA_TEST_APPNAME"] = "abc123def"
        try:
            self.write("x.json", "?appname=abc123def")
            self.write("y.json", "nothing here")
            r = self.put(redactor=ta.Redactor(["TA_TEST_APPNAME"], []))
        finally:
            del os.environ["TA_TEST_APPNAME"]
        marks = {f["path"]: f.get("redacted", False) for f in r["doc"]["files"]}
        self.assertEqual(marks, {"x.json": True, "y.json": False})

    def test_optional_env_skipped_when_unset_and_short_values_refused(self):
        os.environ.pop("TA_TEST_UNSET", None)
        self.assertFalse(ta.Redactor([], [], ["TA_TEST_UNSET"]).active)
        os.environ["TA_TEST_SHORT"] = "abc"
        try:
            with self.assertRaises(ta.ArchiveError):
                ta.Redactor([], [], ["TA_TEST_SHORT"])
        finally:
            del os.environ["TA_TEST_SHORT"]


class GhStoreTests(unittest.TestCase):
    def test_commands_target_the_private_repo_without_clobber(self):
        calls = []

        def runner(args):
            calls.append(args)
            if args[:2] == ["api", "--paginate"] and "assets" in args[2]:
                return "12 a.tar.gz\n3 b.files.json\n"
            if args[0] == "api" and args[1].endswith("/releases/tags/t"):
                return "99\n"
            if args[0] == "api":
                return "orbit-raw-2026-11\nrelief-raw-2026-11\n"
            return ""

        s = ta.GhStore("metacog-osint/tic-archive", runner)
        self.assertEqual(s.tags("orbit-"), ["orbit-raw-2026-11"])
        self.assertEqual(s.assets("t"), {"a.tar.gz": 12, "b.files.json": 3})
        s.upload("t", [Path("x.tar.gz")])
        self.assertTrue(all("--clobber" not in c for c in calls))
        self.assertIn("metacog-osint/tic-archive", calls[-1])


if __name__ == "__main__":
    unittest.main()
