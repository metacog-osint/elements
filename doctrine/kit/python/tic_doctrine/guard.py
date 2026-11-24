"""Stop local machine details reaching a public repo.

    python tic.py guard --base <sha>   check only the lines a pull request adds (and its file names)
    python tic.py guard --all          check every tracked file
    python tic.py guard --hash         read terms from stdin, one per line, and print their hashes

The blocked terms are stored only as salted hashes, so this public file does not list them. Each line is
split into candidate tokens (drive paths, words, word pairs), and each token's hash is looked up. A finding
names the file and line and never echoes the term. To add a term, run --hash and paste the result below.
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

SALT = "tic-guard-v1:"
BLOCKED = frozenset({
    "403869729819a91eb12b12b0",
    "492e301cf9e9941f20226cb8",
    "58b19abc4406ecc9b0cfb72e",
    "622397776ad699d22fc0d3fe",
    "62c7271c71912f8b876b1034",
    "7736224760aba4c13e1f8ecd",
    "ab2539576baec054534450bb",
    "bab06b422217b06807120466",
    "bbe0082345ef8df7aa8faff6",
    "ce586f0a8e106f149a9d8302",
    "ced17e593cb19080cc21811a",
    "d02faba4532ec033685e77cb",
})

DRIVE = re.compile(r"(?<![A-Za-z])([A-Za-z]):[\\/]+([^\\/\s\"'`<>|:*?]+)")
POSIX_DRIVE = re.compile(r"(?<![\w.-])/([a-z])/([\w.~-]+)")
WORD = re.compile(r"[A-Za-z0-9_~-]+")


def digest(term: str) -> str:
    return hashlib.sha256((SALT + term).encode("utf-8")).hexdigest()[:24]


def tokens(line: str):
    """Yield every candidate token of a line. Words appear as written and in lower case."""
    for rx in (DRIVE, POSIX_DRIVE):
        for m in rx.finditer(line):
            yield f"{m.group(1)}:/{m.group(2)}".lower()
    words = WORD.findall(line)
    for i, w in enumerate(words):
        yield w
        yield w.lower()
        if i + 1 < len(words):
            yield f"{w} {words[i + 1]}".lower()


def blocked(line: str, terms=BLOCKED) -> bool:
    return any(digest(t) in terms for t in tokens(line))


def added_lines(diff: str):
    """Yield (path, line number, text) for each added line of a zero-context unified diff, and each new path."""
    path, num = None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            name = raw[4:].strip().strip('"')
            path = None if name == "/dev/null" else name[2:] if name.startswith("b/") else name
            if path:
                yield path, 0, path
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            num = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path:
            yield path, num, raw[1:]
            num += 1


def git(*args) -> str:
    done = subprocess.run(["git", *args], capture_output=True, check=True)
    return done.stdout.decode("utf-8", "replace")


def scan_all():
    for name in git("ls-files", "-z").split("\0"):
        if not name:
            continue
        yield name, 0, name
        p = Path(name)
        if not p.is_file():
            continue
        raw = p.read_bytes()
        if b"\0" in raw[:8000]:
            continue
        for i, text in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            yield name, i, text


def main(argv) -> int:
    if "--hash" in argv:
        for term in sys.stdin.read().splitlines():
            if term.strip():
                print(digest(term.strip()))
        return 0
    if "--all" in argv:
        lines = scan_all()
    elif "--base" in argv and argv.index("--base") + 1 < len(argv):
        base = argv[argv.index("--base") + 1]
        lines = added_lines(git("-c", "core.quotepath=off", "diff", "--unified=0", "--no-color", "--no-ext-diff",
                                base, "HEAD"))
    else:
        print(__doc__)
        return 2
    found = [(path, num) for path, num, text in lines if blocked(text)]
    for path, num in found:
        where = f"{path}:{num}" if num else f"{path} (file name)"
        print(f"guard: {where} has a local path, machine name or private file name. Remove it.")
    print(f"guard: {len(found)} finding(s)")
    return 1 if found else 0
