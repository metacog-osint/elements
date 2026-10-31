"""Doctrine kit command line. Works in the kit repo and in a vendored copy
(doctrine/kit/tic.py), with the standard library only.

    python tic.py lint <feed files> [--doctrine doctrine] [--json report.json]
    python tic.py registers [doctrine]
    python tic.py health doctrine/sources.json [--out doctrine/health.json]
    python tic.py withheld --log private/withheld.jsonl --out site/data/withheld.json
    python tic.py likelihood 0.7
    python tic.py kitcheck          (in a vendored copy: fail if doctrine/kit was edited by hand)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "python"))


def kitcheck() -> int:
    """In a vendored copy: fail if any kit file differs from KIT.json (the copy was edited by hand)."""
    import hashlib
    import json
    here = Path(__file__).resolve().parent
    manifest = here / "KIT.json"
    if not manifest.exists():
        print("kitcheck: no KIT.json here (this is the kit repo, not a vendored copy)")
        return 0
    recorded = json.loads(manifest.read_text(encoding="utf-8"))

    def digest(path):  # CRLF counts as LF, so a Windows checkout (core.autocrlf) still matches
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

    bad = [rel for rel, h in recorded["files"].items() if not (here / rel).exists() or digest(here / rel) != h]
    if bad:
        print("kitcheck: edited or missing in doctrine/kit (change the kit repo and sync instead):", ", ".join(bad))
        return 1
    print(f"kitcheck: doctrine kit {recorded['version']} copy intact ({len(recorded['files'])} files)")
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "lint":
        from tic_doctrine.lint import main as run
    elif cmd == "registers":
        from tic_doctrine.registers import main as run
    elif cmd == "health":
        from tic_doctrine.health import main as run
    elif cmd == "withheld":
        from tic_doctrine.withhold import main as run
    elif cmd == "kitcheck":
        return kitcheck()
    elif cmd == "likelihood":
        from tic_doctrine import likelihood
        for p in rest:
            print(f"{p}: {likelihood.label(float(p))}  [{likelihood.tooltip(float(p))}]")
        return 0
    else:
        print(f"unknown command {cmd!r}\n{__doc__}")
        return 2
    return run(rest)


if __name__ == "__main__":
    sys.exit(main())
