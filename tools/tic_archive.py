#!/usr/bin/env python3
"""tic_archive.py: copy licence-restricted raw data into TIC's private archive, metacog-osint/tic-archive.

Rule: no TIC program loses data. Live views may filter; storage keeps everything. Data whose
licence bars public redistribution (Space-Track, WHO, ReliefWeb, private watch configuration, ...) cannot go into
the public program repos, so it goes here. Same file in every program repo (tools/tic_archive.py); the reference
copy and its tests live in tic-archive itself.

Storage is GitHub release assets in the PRIVATE repo. One release per program, lane and month:
    <program>-<lane>-YYYY-MM          (a full release, 1,000 assets, rolls over to <tag>.2, <tag>.3, ...)
Each `put` takes a snapshot of one folder and uploads:
    <stamp>-<sha12>.tar.gz            files whose content is not in the lane's previous snapshot (deterministic tar)
    <stamp>-<sha12>.files.json        the WHOLE snapshot: every file's path, bytes, sha256 and the asset holding it
<stamp> is the UTC time (YYYYMMDDTHHMMSSZ) and sha12 the content hash, so names are unique and nothing is ever
replaced (no --clobber). A snapshot identical to the previous one is skipped. `restore` rebuilds any snapshot.

Logs of public repos are public: this script prints counts, bytes and asset names only, never file contents or paths.

    python tools/tic_archive.py put --program orbit --lane raw --src data/raw [--exclude 'gcat/*'] [--dry-run]
    python tools/tic_archive.py restore --program orbit --lane raw --dest /tmp/x [--snapshot NAME.files.json]
    python tools/tic_archive.py list --program orbit --lane raw

Credentials: the gh CLI reads GH_TOKEN (in Actions: secrets.TIC_ARCHIVE_TOKEN, a fine-grained token with
contents:write on tic-archive only) or the local gh login (the PC). Every failure exits non-zero with ::error::.
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ.get("TIC_ARCHIVE_REPO", "metacog-osint/tic-archive")
ASSET_LIMIT = 1000          # GitHub's per-release asset limit
ASSET_MARGIN = 10           # roll over before the limit
MAX_TAR_INPUT = 1_500_000_000   # bytes of input per tar; GitHub's asset limit is 2 GiB
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SCHEMA = "tic-archive-snapshot-1"


class ArchiveError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"tic-archive: {msg}", flush=True)


def error(msg: str) -> None:
    # ::error:: makes a red annotation in GitHub Actions; on the PC it is just a log line.
    print(f"::error::tic-archive: {msg}", file=sys.stderr, flush=True)


def utc_stamp(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --- stores ----------------------------------------------------------------------------------------------------

class GhStore:
    """Release assets in a GitHub repo, through the gh CLI."""

    def __init__(self, repo: str = REPO, runner=None):
        self.repo = repo
        self.run = runner or self._run

    @staticmethod
    def _run(args: list[str]) -> str:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            # gh's stderr carries no secrets (it never echoes the token); trim it anyway.
            raise ArchiveError(f"gh {args[0]} {args[1] if len(args) > 1 else ''} failed: {r.stderr.strip()[:400]}")
        return r.stdout

    def tags(self, prefix: str) -> list[str]:
        out = self.run(["api", "--paginate", f"repos/{self.repo}/releases?per_page=100", "--jq", ".[].tag_name"])
        return sorted(t for t in out.split() if t.startswith(prefix))

    def assets(self, tag: str) -> dict[str, int]:
        rid = self.run(["api", f"repos/{self.repo}/releases/tags/{tag}", "--jq", ".id"]).strip()
        out = self.run(["api", "--paginate", f"repos/{self.repo}/releases/{rid}/assets?per_page=100",
                        "--jq", '.[] | "\\(.size) \\(.name)"'])
        found = {}
        for line in out.splitlines():
            if line.strip():
                size, _, name = line.strip().partition(" ")
                found[name] = int(size)
        return found

    def create(self, tag: str) -> None:
        try:
            self.run(["release", "create", tag, "-R", self.repo, "--title", tag, "--latest=false", "--notes",
                      "TIC private archive (tools/tic_archive.py). Licence-restricted: never redistribute."])
        except ArchiveError:
            # Two runs may race to create the same month's release; if it exists now, carry on.
            if tag not in self.tags(tag):
                raise

    def upload(self, tag: str, paths: list[Path]) -> None:
        self.run(["release", "upload", tag, "-R", self.repo, *[str(p) for p in paths]])

    def download(self, tag: str, name: str, dest_dir: Path) -> Path:
        self.run(["release", "download", tag, "-R", self.repo, "-p", name, "-D", str(dest_dir)])
        return Path(dest_dir) / name


class DirStore:
    """A local stand-in for tests: <root>/<tag>/<asset>."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def tags(self, prefix: str) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and p.name.startswith(prefix))

    def assets(self, tag: str) -> dict[str, int]:
        d = self.root / tag
        if not d.is_dir():
            raise ArchiveError(f"release {tag} not found")
        return {p.name: p.stat().st_size for p in d.iterdir()}

    def create(self, tag: str) -> None:
        (self.root / tag).mkdir(exist_ok=True)

    def upload(self, tag: str, paths: list[Path]) -> None:
        d = self.root / tag
        if not d.is_dir():
            raise ArchiveError(f"release {tag} not found")
        for p in paths:
            if (d / p.name).exists():
                raise ArchiveError(f"asset {p.name} already exists")  # gh behaves the same without --clobber
            shutil.copyfile(p, d / p.name)

    def download(self, tag: str, name: str, dest_dir: Path) -> Path:
        src = self.root / tag / name
        if not src.exists():
            raise ArchiveError(f"asset {name} not in {tag}")
        shutil.copyfile(src, Path(dest_dir) / name)
        return Path(dest_dir) / name


# --- snapshot --------------------------------------------------------------------------------------------------

def check_name(kind: str, value: str) -> None:
    if not NAME_RE.match(value):
        raise ArchiveError(f"{kind} {value!r} must be lower-case letters, digits and hyphens")


def lane_prefix(program: str, lane: str) -> str:
    return f"{program}-{lane}-"


def tag_month(tag: str, prefix: str) -> str:
    return tag[len(prefix):len(prefix) + 7]


def tag_sort_key(tag: str, prefix: str):
    rest = tag[len(prefix):]
    month, _, part = rest.partition(".")
    return (month, int(part) if part.isdigit() else 1)


class Redactor:
    """Removes a secret echoed back by a source (ReliefWeb echoes the appname in href/links) before archiving."""

    def __init__(self, env_names: list[str], params: list[str], optional_env: list[str] = ()):
        from urllib.parse import quote, quote_plus
        self.values: list[bytes] = []
        for name in [*env_names, *optional_env]:
            v = os.environ.get(name, "")
            if not v.strip():
                if name in optional_env:
                    continue          # not set, so the collection never had it to leak
                raise ArchiveError(f"--redact-env {name}: the variable is empty, so the archive would keep it "
                                   "unredacted; pass it to this step")
            if len(v) < 8:
                raise ArchiveError(f"--redact-env {name}: under 8 characters, too short to replace safely")
            for form in {v, quote(v, safe=""), quote_plus(v)}:
                self.values.append(form.encode("utf-8"))
        self.params = [re.compile(rb"(?i)\b(" + re.escape(p.encode()) + rb")=[^&\"'\s<>#;]+") for p in params]

    @property
    def active(self) -> bool:
        return bool(self.values or self.params)

    def apply(self, data: bytes) -> bytes:
        for v in sorted(self.values, key=len, reverse=True):
            data = data.replace(v, b"REDACTED")
        for rx in self.params:
            data = rx.sub(rb"\1=REDACTED", data)
        return data

    def file_bytes(self, p: Path) -> tuple[bytes, bool]:
        """(bytes to archive, whether anything was replaced). A .gz file is redacted inside the gzip."""
        raw = p.read_bytes()
        if p.name.endswith(".gz"):
            try:
                inner = gzip.decompress(raw)
            except OSError:
                inner = None
            if inner is not None:
                red = self.apply(inner)
                return (raw, False) if red == inner else (gzip.compress(red, 6, mtime=0), True)
        red = self.apply(raw)
        return red, red != raw


def parse_sources(src) -> list[tuple[str, Path]]:
    """One folder (a path), or several as [(name, path)] / ["name=path"]; a named folder's files are under name/."""
    if isinstance(src, (str, Path)):
        return [("", Path(src))]
    out = []
    for s in src:
        if isinstance(s, str):
            name, sep, path = s.partition("=")
            if not sep:
                if len(src) > 1:
                    raise ArchiveError(f"with several --src, name each one (name=path): {s}")
                name, path = "", s
            s = (name, path)
        name, path = s
        if name:
            check_name("source name", name)
        out.append((name, Path(path)))
    if len({n for n, _ in out}) != len(out):
        raise ArchiveError("source names must be unique")
    return out


def scan(src, include: list[str], exclude: list[str], redactor: Redactor | None) -> list[dict]:
    """Every regular file under the source folder(s) (symlinks skipped), as posix relative paths, sorted."""
    files = []
    for name, root in parse_sources(src):
        files.extend(_scan_one(root, name, include, exclude, redactor))
    return sorted(files, key=lambda f: f["path"])


def _scan_one(src: Path, name: str, include, exclude, redactor) -> list[dict]:
    files = []
    for p in sorted(src.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        rel = p.relative_to(src).as_posix()
        if name:
            rel = f"{name}/{rel}"
        if include and not any(fnmatch.fnmatch(rel, g) for g in include):
            continue
        if any(fnmatch.fnmatch(rel, g) for g in exclude):
            continue
        if redactor is not None and redactor.active:
            data, changed = redactor.file_bytes(p)
            f = {"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "_data": data}
            if changed:
                f["redacted"] = True      # the archived bytes differ from the fetched ones (index.jsonl's sha256)
            files.append(f)
        else:
            files.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha256_file(p), "_src": p})
    return files


def snapshot_hash(files: list[dict]) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(f"{f['path']}\0{f['sha256']}\n".encode("utf-8"))
    return h.hexdigest()


def write_tar(members: list[dict], dest: Path) -> None:
    """Deterministic tar.gz: sorted members, mtime 0, owner 0, mode 0644, gzip mtime 0."""
    with open(dest, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as t:
            for f in sorted(members, key=lambda m: m["member"]):
                ti = tarfile.TarInfo(f["member"])
                ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = f["bytes"], 0, 0o644, 0, 0, "", ""
                if "_data" in f:
                    t.addfile(ti, io.BytesIO(f["_data"]))
                else:
                    with open(f["_src"], "rb") as fh:
                        t.addfile(ti, fh)


def chunks(files: list[dict], limit: int) -> list[list[dict]]:
    out, cur, size = [], [], 0
    for f in files:
        if f["bytes"] > limit:
            raise ArchiveError(f"a file of {f['bytes']:,} bytes is over the {limit:,}-byte tar limit")
        if cur and size + f["bytes"] > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(f)
        size += f["bytes"]
    if cur:
        out.append(cur)
    return out


class Archive:
    def __init__(self, store, program: str, lane: str):
        check_name("program", program)
        check_name("lane", lane)
        self.store, self.program, self.lane = store, program, lane
        self.prefix = lane_prefix(program, lane)

    # The previous snapshot is the newest files.json in the lane, in any month.
    def latest(self, workdir: Path) -> dict | None:
        tags = sorted(self.store.tags(self.prefix), key=lambda t: tag_sort_key(t, self.prefix), reverse=True)
        for tag in tags:
            names = sorted(n for n in self.store.assets(tag) if n.endswith(".files.json"))
            if names:
                p = self.store.download(tag, names[-1], workdir)
                doc = json.loads(p.read_text(encoding="utf-8"))
                if doc.get("schema") != SCHEMA:
                    raise ArchiveError(f"{names[-1]}: unknown schema {doc.get('schema')!r}")
                return doc
        return None

    def target_tag(self, month: str, need: int) -> tuple[str, dict[str, int]]:
        """This month's release with room for `need` more assets, creating it (or the next part) if needed."""
        base = f"{self.prefix}{month}"
        existing = [t for t in self.store.tags(base) if t == base or t.startswith(base + ".")]
        parts = sorted(existing, key=lambda t: tag_sort_key(t, self.prefix))
        if parts:
            tag = parts[-1]
            assets = self.store.assets(tag)
            if len(assets) + need <= ASSET_LIMIT - ASSET_MARGIN:
                return tag, assets
            n = tag_sort_key(tag, self.prefix)[1] + 1
            tag = f"{base}.{n}"
        else:
            tag = base
        self.store.create(tag)
        return tag, self.store.assets(tag)

    def put(self, src: Path, include=(), exclude=(), redactor: Redactor | None = None, dry_run=False,
            min_interval_hours: float = 0, now: datetime | None = None, max_tar_input: int = MAX_TAR_INPUT) -> dict:
        for _, root in parse_sources(src):
            if not root.is_dir():
                raise ArchiveError(f"source folder {root} does not exist")
        now = now or datetime.now(timezone.utc)
        stamp = utc_stamp(now)
        files = scan(src, list(include), list(exclude), redactor)
        if not files:
            raise ArchiveError("the source folder(s) hold no files to archive (after include/exclude)")
        snap = snapshot_hash(files)
        with tempfile.TemporaryDirectory(prefix="tic-archive-") as td:
            work = Path(td)
            prev = self.latest(work)
            if prev and prev.get("snapshot_sha256") == snap:
                log(f"{self.prefix}*: unchanged since {prev['stamp']} ({len(files)} files); nothing uploaded")
                return {"status": "unchanged", "files": len(files)}
            if prev and min_interval_hours:
                age = (now - datetime.strptime(prev["stamp"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc))
                if age.total_seconds() < min_interval_hours * 3600:
                    log(f"{self.prefix}*: last snapshot {prev['stamp']} is under {min_interval_hours:g} h old; skipped")
                    return {"status": "too-soon", "files": len(files)}
            where = {}
            for f in (prev or {}).get("files", []):
                where.setdefault(f["sha256"], (f["release"], f["asset"], f["member"]))
            new, seen_new = [], {}
            for f in files:
                if f["sha256"] in where:
                    continue
                if f["sha256"] in seen_new:      # same bytes twice in this snapshot: store once
                    continue
                seen_new[f["sha256"]] = f
                f["member"] = f"{f['sha256'][:2]}/{f['sha256']}"
                new.append(f)
            groups = chunks(new, max_tar_input) if new else []
            tag, assets = (None, {}) if dry_run else self.target_tag(now.strftime("%Y-%m"), len(groups) + 1)
            tag = tag or f"{self.prefix}{now.strftime('%Y-%m')}"
            uploads = []
            for i, g in enumerate(groups):
                if dry_run:      # no tar is built (it may be GBs): the part is named by its number only
                    for f in g:
                        where[f["sha256"]] = (tag, f"{stamp}-part{i}.tar.gz", f["member"])
                    continue
                tmp = work / f"part{i}.tar.gz"
                write_tar(g, tmp)
                name = f"{stamp}-{sha256_file(tmp)[:12]}.tar.gz"
                if name in assets:
                    raise ArchiveError(f"asset {name} already exists in {tag}")
                final = work / name
                tmp.rename(final)
                uploads.append(final)
                for f in g:
                    where[f["sha256"]] = (tag, name, f["member"])
            doc = {"schema": SCHEMA, "program": self.program, "lane": self.lane, "stamp": stamp,
                   "snapshot_sha256": snap, "file_count": len(files), "bytes": sum(f["bytes"] for f in files),
                   "new_files": len(new), "new_bytes": sum(f["bytes"] for f in new),
                   "previous": prev["stamp"] if prev else None,
                   "files": [{"path": f["path"], "bytes": f["bytes"], "sha256": f["sha256"],
                              "release": where[f["sha256"]][0], "asset": where[f["sha256"]][1],
                              "member": where[f["sha256"]][2], **({"redacted": True} if f.get("redacted") else {})}
                             for f in files]}
            index = work / f"{stamp}-{snap[:12]}.files.json"
            index.write_text(json.dumps(doc, indent=0, sort_keys=True) + "\n", encoding="utf-8")
            sizes = {p.name: p.stat().st_size for p in uploads + [index]}
            if dry_run:
                log(f"dry run {tag}: {len(files)} files, {len(new)} new ({doc['new_bytes']:,} bytes) in "
                    f"{len(groups)} tar(s) and one index")
                return {"status": "dry-run", "tag": tag, "assets": sizes, "doc": doc}
            # Tars first, then the index, so an index on the release always means its tars are there.
            if uploads:
                self._upload_checked(tag, uploads)
            self._upload_checked(tag, [index])
            log(f"{tag}: snapshot {stamp}, {len(files)} files ({doc['bytes']:,} bytes), {len(new)} new "
                f"({doc['new_bytes']:,} bytes); uploaded {', '.join(f'{n} ({s:,} B)' for n, s in sizes.items())}")
            return {"status": "uploaded", "tag": tag, "assets": sizes, "doc": doc}

    def _upload_checked(self, tag: str, paths: list[Path]) -> None:
        want = {p.name: p.stat().st_size for p in paths}
        last = None
        for attempt in range(3):
            try:
                self.store.upload(tag, paths)
                last = None
                break
            except ArchiveError as e:
                last = e
                have = self.store.assets(tag)
                paths = [p for p in paths if have.get(p.name) != want[p.name]]
                if not paths:
                    last = None
                    break
                time.sleep(5 * (attempt + 1))
        if last is not None:
            raise last
        have = self.store.assets(tag)
        bad = [n for n, s in want.items() if have.get(n) != s]
        if bad:
            raise ArchiveError(f"upload to {tag} did not verify: {', '.join(bad)}")

    def restore(self, dest: Path, snapshot: str | None = None) -> dict:
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tic-archive-") as td:
            work = Path(td)
            if snapshot:
                tag = next((t for t in self.store.tags(self.prefix) if snapshot in self.store.assets(t)), None)
                if tag is None:
                    raise ArchiveError(f"snapshot {snapshot} not found")
                doc = json.loads(self.store.download(tag, snapshot, work).read_text(encoding="utf-8"))
            else:
                doc = self.latest(work)
                if doc is None:
                    raise ArchiveError(f"no snapshots for {self.prefix}*")
            opened: dict[tuple[str, str], tarfile.TarFile] = {}
            try:
                for f in doc["files"]:
                    key = (f["release"], f["asset"])
                    if key not in opened:
                        opened[key] = tarfile.open(self.store.download(f["release"], f["asset"], work), "r:gz")
                    out = (dest / f["path"]).resolve()
                    if dest.resolve() not in out.parents:
                        raise ArchiveError(f"refusing a path outside {dest}")
                    data = opened[key].extractfile(f["member"]).read()
                    if hashlib.sha256(data).hexdigest() != f["sha256"]:
                        raise ArchiveError(f"sha256 mismatch for a member of {f['asset']}")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(data)
            finally:
                for t in opened.values():
                    t.close()
        log(f"restored snapshot {doc['stamp']} of {self.prefix}*: {len(doc['files'])} files")
        return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("put", "restore", "list"):
        s = sub.add_parser(name)
        s.add_argument("--program", required=True)
        s.add_argument("--lane", required=True)
        if name == "put":
            s.add_argument("--src", action="append", required=True,
                           help="folder to snapshot; repeat as name=path for several (files go under name/)")
            s.add_argument("--include", action="append", default=[], help="glob on the relative path (repeat)")
            s.add_argument("--exclude", action="append", default=[], help="glob on the relative path (repeat)")
            s.add_argument("--redact-env", action="append", default=[],
                           help="env var whose value is replaced by REDACTED in every file (must be set)")
            s.add_argument("--redact-env-if-set", action="append", default=[],
                           help="as --redact-env, but an unset variable is skipped")
            s.add_argument("--redact-param", action="append", default=[],
                           help="query parameter whose value is replaced by REDACTED (e.g. appname)")
            s.add_argument("--min-interval-hours", type=float, default=0)
            s.add_argument("--dry-run", action="store_true")
        if name == "restore":
            s.add_argument("--dest", required=True)
            s.add_argument("--snapshot", help="a .files.json asset name; default the newest")
    a = ap.parse_args(argv)
    try:
        arch = Archive(GhStore(), a.program, a.lane)
        if a.cmd == "put":
            red = Redactor(a.redact_env, a.redact_param, a.redact_env_if_set)
            arch.put(a.src, a.include, a.exclude, red, a.dry_run, a.min_interval_hours)
        elif a.cmd == "restore":
            arch.restore(Path(a.dest), a.snapshot)
        else:
            for t in sorted(arch.store.tags(arch.prefix), key=lambda t: tag_sort_key(t, arch.prefix)):
                assets = arch.store.assets(t)
                n_snap = sum(1 for n in assets if n.endswith(".files.json"))
                print(f"{t}\t{len(assets)} assets\t{n_snap} snapshots\t{sum(assets.values()):,} bytes")
        return 0
    except (ArchiveError, OSError) as e:
        error(f"{a.cmd} {a.program}/{a.lane}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
