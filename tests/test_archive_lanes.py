"""Private archive lanes: every file a run of update.yml writes beside the tracked code (data/, history/, the FIRMS
cell files in .firms-cells/, site/) lands in the private archive (tools/tic_archive.py, metacog-osint/tic-archive)
and restores byte for byte. That includes the files git never keeps (data/firms.json, data/meteoalarm.json,
data/nws_recent.json, .firms-cells/), and a file a later run removes or rewrites stays restorable from the snapshot
that held it.

The test makes two offline runs, a day apart, in a temporary folder with Elements' own code: the collection's files
(written with elements.common.save, as `collect` writes them, from small made-up records), the history step
(log_history), the FIRMS cell store (store_run, with gh replaced) and the build. The second run closes the first
day's log file (gzipped, the plain file removed), rewrites the state and stores another hour of FIRMS cells. After
each run the workflow's own tic_archive.py commands, read from update.yml, run against a local DirStore. Nothing
reaches GitHub: GhStore is replaced by the DirStore and any subprocess call during an archive command fails the
test."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.append(str(ROOT / "tools"))   # after ROOT: tools/elements.py must not shadow the elements package
import tic_archive as ta  # noqa: E402
from elements import common, firms, firms_store, meteoalarm  # noqa: E402
from test_elements import dataset  # noqa: E402
from test_firms_store import FakeGh  # noqa: E402
from test_meteoalarm import FINLAND, FRANCE, GERMANY  # noqa: E402

_spec = importlib.util.spec_from_file_location("elements_cli_lanes", ROOT / "tools" / "elements.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

WF = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
PROGRAM = "elements"
LANES = {"history": "history", "data": "data", "firms-cells": ".firms-cells", "site": "site"}   # lane: folder
RUN1 = datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc)
RUN2 = RUN1 + timedelta(days=1, minutes=30)
STAMP = {RUN1: "20261105T191000Z", RUN2: "20261106T194000Z"}
NOT_RUN_OUTPUTS = {"__pycache__/", "*.pyc", ".claude/", "reviews/"}   # .gitignore lines that are not run outputs


def steps() -> dict[str, str]:
    """The update job's steps by name (unnamed steps by their id, else their action)."""
    job = WF.split("\n  update:\n", 1)[1].split("\n    steps:\n", 1)[1]
    out = {}
    for chunk in re.split(r"(?m)^      - ", job)[1:]:
        m = re.match(r"name: (.+)|id: (\S+)|uses: (\S+)", chunk)
        out[(m.group(1) or m.group(2) or m.group(3)).strip()] = chunk
    return out


STEPS = steps()


def step(prefix: str) -> str:
    (name,) = [n for n in STEPS if n.startswith(prefix)]
    return STEPS[name]


ARCHIVE_STEP = "Private archive (history, data, FIRMS cells and site, to tic-archive)"


def archive_calls(text: str, cmd: str) -> list[list[str]]:
    """Every `python tools/tic_archive.py <cmd> ...` in a step, as argv after the script name."""
    flat = text.replace("\\\n", " ")
    return [[m.group(1), *shlex.split(m.group(2))]
            for m in re.finditer(r"python tools/tic_archive\.py (" + cmd + r")\b([^;|&\n]*)", flat)]


def arg(argv: list[str], flag: str) -> list[str]:
    return [argv[i + 1] for i, t in enumerate(argv) if t == flag]


def put_calls() -> list[list[str]]:
    return archive_calls(STEPS[ARCHIVE_STEP], "put")


def tree(root: Path) -> dict[str, str]:
    """{posix path relative to root: sha256} for every file."""
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def run_archive(argv: list[str], cwd: Path, store: Path, stamp: str, env: dict | None = None) -> int:
    """One tic_archive.py command as the workflow gives it, in cwd, against a DirStore at store."""
    def no_subprocess(*a, **k):
        raise AssertionError("an archive command tried to run a subprocess (gh): nothing may leave the test")

    old = os.getcwd()
    os.chdir(cwd)
    try:
        clean = {k: v for k, v in os.environ.items() if k not in ("FIRMS_MAP_KEY", "GH_TOKEN")} | (env or {})
        with mock.patch.dict(os.environ, clean, clear=True), \
                mock.patch.object(ta, "GhStore", lambda *a, **k: ta.DirStore(store)), \
                mock.patch.object(ta, "utc_stamp", lambda now=None: stamp), \
                mock.patch.object(subprocess, "run", no_subprocess):
            return ta.main(argv)
    finally:
        os.chdir(old)


def collect_files(when: datetime, second: bool) -> None:
    """The collection's files, written with Elements' own save() and health() as `collect` writes them."""
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    d = dataset()
    if second:
        d["usgs"]["records"] = d["usgs"]["records"][1:]       # one earthquake left the feed: an ended line
    for k, src in cli.LANES.items():
        recs = d.get(k, {}).get("records")
        if k == "meteoalarm":
            recs = (meteoalarm.parse(GERMANY, "germany", when) + meteoalarm.parse(FRANCE, "france", when)
                    + meteoalarm.parse(FINLAND, "finland", when))
        elif k == "firms":
            recs = firms_payload(when)
        elif k == "usdm":
            recs = {}
        common.save(f"{k}.json", {"records": recs if recs is not None else []}, compact=k in cli.COMPACT)
        common.health(src, True, "made-up records", stamp)
    common.save("nws_recent.json", {"fetched_at": stamp, "start": stamp, "error": None, "active_error": None,
                                    "records": []})
    common.save("firms_daily.json", firms.update_history(common.load("firms_daily.json", {}), firms_payload(when),
                                                         stamp[:10]))


def firms_payload(end: datetime) -> dict:
    """A FIRMS read as collect_firms leaves it: cells, daily counts, low-confidence cells, how and key counts."""
    dets = [(10.1, 20.1, end - timedelta(hours=2), True, 5.0), (30.2, 40.2, end - timedelta(hours=30), False, 1.0)]
    low = [(11.1, 21.1, end - timedelta(hours=3), False, 0.5)]
    p = firms.aggregate(dets, end)
    p["via"] = {"VIIRS_NOAA20_NRT": "api"}
    p["rows"] = {"VIIRS_NOAA20_NRT": 3}
    p["low"] = {k: v for k, v in firms.aggregate(low, end).items() if k != "daily"}
    p["key_status"] = {"current_transactions": 7}
    return p


def offline_run(root: Path, when: datetime, second: bool) -> None:
    """One run as update.yml makes it: collect, history, FIRMS store, build. A fresh runner each time, so
    .firms-cells/ holds only this run's files."""
    shutil.rmtree(root / ".firms-cells", ignore_errors=True)
    with mock.patch.object(common, "DATA", root / "data"), mock.patch.object(cli, "HIST", root / "history"), \
            mock.patch.object(cli, "OUT", root / "site"):
        collect_files(when, second)
        cli.log_history(when)
        line = firms_store.store_run(common.load("firms.json")["records"], root / ".firms-cells",
                                     now=when + timedelta(minutes=5), run=FakeGh())
        assert "stored" in line, line
        cli.build()


class TestWorkflowLanes(unittest.TestCase):
    def test_lanes_are_history_data_firms_cells_site(self):
        lanes = {arg(c, "--lane")[0]: c for c in put_calls()}
        self.assertEqual({k: arg(c, "--src") for k, c in lanes.items()}, {k: [v] for k, v in LANES.items()})
        for c in lanes.values():
            self.assertEqual(arg(c, "--program"), [PROGRAM])
            self.assertEqual(arg(c, "--exclude") + arg(c, "--include"), [])
        # Copies of public files and of this run's own files: archived as they are, so they match by hash. data/
        # is scanned for the FIRMS key only (it never reaches data/; the Redactor leaves other bytes alone).
        self.assertEqual([t for t in lanes["data"] if t.startswith("--redact")], ["--redact-env-if-set"])
        self.assertEqual(arg(lanes["data"], "--redact-env-if-set"), ["FIRMS_MAP_KEY"])
        for lane in ("history", "firms-cells", "site"):
            self.assertFalse([t for t in lanes[lane] if t.startswith("--redact")], lane)

    def test_step_is_last_after_the_deploy_and_loud_on_failure(self):
        names = list(STEPS)
        self.assertEqual(names[-1], ARCHIVE_STEP)
        for before in ("deployment_last", "Fail the run if history or the push failed", "Store this hour's FIRMS cells",
                       "Commit data and history when their content changed"):
            self.assertLess(names.index(before), names.index(ARCHIVE_STEP), before)
        text = STEPS[ARCHIVE_STEP]
        self.assertIn("if: ${{ !cancelled() }}", text)
        self.assertIn("GH_TOKEN: ${{ secrets.TIC_ARCHIVE_TOKEN }}", text)
        self.assertNotIn("github.token", text)
        self.assertNotIn("|| true", text)
        self.assertNotIn("continue-on-error", text)
        self.assertIn('[ -z "$GH_TOKEN" ]', text)
        self.assertEqual(text.count("exit 1"), 2)            # token missing; any lane failed
        self.assertEqual(text.count("|| failed=1"), 4)       # each lane tried even if another failed

    def test_each_lane_only_after_the_step_that_writes_it(self):
        text = STEPS[ARCHIVE_STEP]
        self.assertIn("COLLECTED: ${{ steps.collect.outcome }}", text)
        self.assertIn("HISTORY: ${{ steps.history.outcome }}", text)
        self.assertIn("DEPLOYED: ${{ steps.deployment.outcome == 'success' || steps.deployment_retry.outcome == "
                      "'success' || steps.deployment_last.outcome == 'success' }}", text)
        self.assertIn("id: collect", STEPS["Collect"])
        self.assertIn("id: history", step("History"))
        self.assertIn("continue-on-error: true", step("History"))   # so its outcome, not its conclusion, is read
        for i in ("deployment", "deployment_retry", "deployment_last"):
            self.assertIn(i, STEPS)
        flat = text.replace("\\\n", " ")
        gate = {"history": r'if \[ "\$HISTORY" = "success" \]; then',
                "data": r'if \[ "\$COLLECTED" = "success" \]; then',
                "firms-cells": r'if \[ -d \.firms-cells \] && \[ -n "\$\(ls -A \.firms-cells\)" \]; then',
                "site": r'if \[ "\$DEPLOYED" = "true" \]; then'}
        for lane, cond in gate.items():
            self.assertRegex(flat, cond + r"\s+python tools/tic_archive\.py put --program elements --lane " + lane + " ")

    def test_every_run_output_is_inside_an_archived_folder(self):
        # Where the code writes: data/ (collect), history/ (history), .firms-cells/ (firms-store), site/ (build).
        self.assertEqual(common.DATA, ROOT / "data")
        self.assertEqual(cli.HIST, ROOT / "history")
        self.assertEqual(cli.OUT, ROOT / "site")
        self.assertIn('ROOT / ".firms-cells"', (ROOT / "tools" / "elements.py").read_text(encoding="utf-8"))
        # What the workflow commits and deploys.
        self.assertIn("git add data history\n", STEPS["Commit data and history when their content changed"])
        self.assertIn("with: { path: site }", STEPS["actions/upload-pages-artifact@v3"])
        # The files git never keeps: each one is a run output inside an archived folder. A new ignored output
        # outside them fails here.
        folders = [v.rstrip("/") + "/" for v in LANES.values()]
        lines = [x.strip() for x in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
                 if x.strip() and not x.startswith("#")]
        outputs = [x for x in lines if x not in NOT_RUN_OUTPUTS]
        self.assertEqual(sorted(outputs), sorted(["site/", "data/firms.json", ".firms-cells/", "data/meteoalarm.json",
                                                  "data/nws_recent.json"]))
        for x in outputs:
            self.assertTrue(any(x == f or x.startswith(f) for f in folders), x)


class TestEveryRunFileIsArchived(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix="elements-lanes-"))
        cls.root, cls.store = cls.work / "run", cls.work / "store"
        cls.root.mkdir()
        cls.trees, cls.results = {}, {}
        for when, second in ((RUN1, False), (RUN2, True)):
            offline_run(cls.root, when, second)
            cls.trees[when] = {lane: tree(cls.root / src) for lane, src in LANES.items()}
            cls.results[when] = {arg(a, "--lane")[0]: run_archive(a, cls.root, cls.store, STAMP[when])
                                 for a in put_calls()}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def snapshot(self, lane: str, when: datetime) -> str:
        (name,) = [p.name for p in (self.store / f"{PROGRAM}-{lane}-{when:%Y-%m}").iterdir()
                   if p.name.startswith(STAMP[when]) and p.name.endswith(".files.json")]
        return name

    def restore(self, lane: str, when: datetime | None = None) -> dict[str, str]:
        """A lane restored into a temporary folder (the newest snapshot, or the one of that run): {path: sha256}."""
        with tempfile.TemporaryDirectory() as td:
            cmd = ["restore", "--program", PROGRAM, "--lane", lane, "--dest", td]
            if when is not None:
                cmd += ["--snapshot", self.snapshot(lane, when)]
            self.assertEqual(run_archive(cmd, self.root, self.store, "unused"), 0, lane)
            return tree(Path(td))

    def test_the_offline_run_writes_only_the_archived_folders(self):
        self.assertEqual({p.name for p in self.root.iterdir()}, set(LANES.values()))
        for when in (RUN1, RUN2):
            self.assertTrue(all(self.trees[when].values()), when)

    def test_every_put_succeeded(self):
        self.assertEqual(self.results, {w: {lane: 0 for lane in LANES} for w in (RUN1, RUN2)})

    def test_every_file_of_each_run_restores_byte_for_byte(self):
        for when in (RUN1, RUN2):
            for lane in LANES:
                self.assertEqual(self.restore(lane, when), self.trees[when][lane], f"{lane} at {when}")
        newest = {lane: self.restore(lane) for lane in LANES}
        self.assertEqual(newest, self.trees[RUN2])

    def test_the_files_git_does_not_keep_are_archived(self):
        data = self.restore("data", RUN1)
        for p in ("firms.json", "meteoalarm.json", "nws_recent.json", "health.json", "firms_daily.json", "usgs.json"):
            self.assertIn(p, data)
        self.assertEqual(sorted(self.restore("firms-cells", RUN1)),
                         ["firms-cells-20261105T19Z.json.gz", "firms-low-cells-20261105T19Z.json.gz"])
        site = self.restore("site", RUN1)
        for p in ("index.html", "data/feed.geojson", "data/ended.geojson", "data/fires.json", "data/meteoalarm.json"):
            self.assertIn(p, site)

    def test_the_firms_cell_files_are_the_bytes_the_release_gets(self):
        # The store writes the file it uploads; the lane archives that same file, so a restore matches the release.
        payload = firms_payload(RUN2)
        want = hashlib.sha256(firms_store.encode(firms_store.snapshot(payload))).hexdigest()
        self.assertEqual(self.restore("firms-cells", RUN2)["firms-cells-20261106T19Z.json.gz"], want)

    def test_removed_or_rewritten_files_stay_restorable(self):
        first, second = self.restore("history", RUN1), self.restore("history", RUN2)
        # The first day's log: plain while it was today, gzipped and the plain file removed once it closed.
        day1 = "log/2026/11/05.jsonl"
        self.assertIn(day1, first)
        self.assertNotIn(day1, second)
        self.assertIn(day1 + ".gz", second)
        self.assertNotIn(day1, self.trees[RUN2]["history"])
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(run_archive(["restore", "--program", PROGRAM, "--lane", "history", "--dest", td,
                                          "--snapshot", self.snapshot("history", RUN1)], self.root, self.store, "x"), 0)
            plain = (Path(td) / day1).read_bytes()
        self.assertEqual(gzip.decompress((self.root / "history" / (day1 + ".gz")).read_bytes()), plain)
        # The open items, rewritten each run: both versions restore.
        self.assertNotEqual(first["state.json"], second["state.json"])
        self.assertEqual(first["state.json"], self.trees[RUN1]["history"]["state.json"])
        # The yellow MeteoAlarm day file, closed by the second run.
        self.assertIn("meteoalarm/2026-11-05.jsonl", first)
        self.assertIn("meteoalarm/2026-11-05.jsonl.gz", second)
        # Each run's FIRMS cells: the first hour's files are gone from the second run's folder, not from the archive.
        self.assertTrue(all("20261106T" in p for p in self.trees[RUN2]["firms-cells"]))
        self.assertTrue(all("20261105T" in p for p in self.restore("firms-cells", RUN1)))
        # The data and the deployed site of the first run, both replaced by the second.
        for lane in ("data", "site"):
            self.assertNotEqual(self.trees[RUN1][lane], self.trees[RUN2][lane], lane)
            self.assertEqual(self.restore(lane, RUN1), self.trees[RUN1][lane], lane)


class TestDataLaneRedaction(unittest.TestCase):
    """The data lane removes the FIRMS key, should a copy ever reach data/, and leaves every other byte alone."""

    def test_key_redacted_and_other_files_unchanged(self):
        (call,) = [c for c in put_calls() if arg(c, "--lane") == ["data"]]
        key = "0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "data").mkdir()
            (td / "data" / "health.json").write_text('{"nasa-firms": {"detail": "MAP_KEY=%s"}}\n' % key)
            (td / "data" / "usgs.json").write_text('{"records": []}\n')
            self.assertEqual(run_archive(call, td, td / "store", STAMP[RUN1], {"FIRMS_MAP_KEY": key}), 0)
            self.assertEqual(run_archive(["restore", "--program", PROGRAM, "--lane", "data", "--dest",
                                          str(td / "back")], td, td / "store", "x"), 0)
            self.assertEqual((td / "back" / "health.json").read_text(), '{"nasa-firms": {"detail": "MAP_KEY=REDACTED"}}\n')
            self.assertEqual((td / "back" / "usgs.json").read_bytes(), (td / "data" / "usgs.json").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=1)
