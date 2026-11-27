"""No personal name in the repository's own files, apart from copyright lines."""
import hashlib
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# LICENSE and NOTICE carry the copyright holder; doctrine/kit/ and tools/tic_archive.py are shared copies kept
# identical to their source repositories; catalog/us_counties.json is Census data with county names.
SKIP = ("doctrine/kit/", "tools/tic_archive.py", "catalog/us_counties.json", "LICENSE", "NOTICE")
# Lower-case words, by SHA-256, so this file does not hold them.
WORDS = frozenset({
    "e1608f75c5d7813f3d4031cb30bfb786507d98137538ff8e128a6ff74e84e643",
    "1e79f6794931ef59a7825ea40e5b00346d48e7b6a9ada0904a3b9738b2baca92",
})


def hits(text):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("Copyright "):
            continue
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", line)
        if any(hashlib.sha256(w.lower().encode()).hexdigest() in WORDS for w in re.findall(r"[A-Za-z]+", spaced)):
            found.append(number)
    return found


class NoNames(unittest.TestCase):
    def test_detects_a_listed_word_and_skips_copyright_lines(self):
        word = "".join(("T", "om"))
        self.assertEqual(hits("a\nset by " + word + "'s rule\nby" + word + " x\nCopyright 2026 " + word), [2, 3])
        self.assertEqual(hits("atom bottom custom"), [])

    def test_tracked_files_hold_no_personal_name(self):
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        bad = []
        for name in listed.decode("utf-8").split("\0"):
            if not name or name.startswith(SKIP) or not (ROOT / name).is_file():
                continue
            data = (ROOT / name).read_bytes()
            if b"\0" in data:
                continue
            bad += [f"{name}:{n}" for n in hits(data.decode("utf-8", "replace"))]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
