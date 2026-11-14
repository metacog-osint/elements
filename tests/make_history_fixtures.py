"""Write tests/fixtures/history/ from recorded data: Elements' own git history of data/ and one recorded response of
NWS's alerts API. Nothing is invented; files are trimmed to the records the tests need, kept as recorded.

    python tests/make_history_fixtures.py PATH_TO_RECORDED_NWS_ALERTS_SINCE.json

The NWS file is the body of https://api.weather.gov/alerts?start=2026-11-13T00:00:00Z&status=actual&message_type=alert
&severity=Severe,Extreme&limit=500, fetched 14 Nov 2026 about 01:45 UTC."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "history"


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def show(sha, name):
    return json.loads(git("show", f"{sha}:data/{name}"))


def commit_before(when: str, path: str) -> str:
    return git("log", "-1", "--format=%H", f"--before={when}", "origin/main", "--", path).strip()


def main(nws_since_path: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"made_by": "tests/make_history_fixtures.py", "files": {}}

    # 1. A Severe Thunderstorm Warning that left the feed: data commits d0fe961 (01 Nov 23:50:24Z) and efb55be
    #    (02 Nov 06:42:24Z), the next data commit. Kept: that warning and two NWS events present in both runs.
    a, b = "d0fe9614f5a80a7c186aa9144842b35d91542a86", "efb55be479fed00a0f12af2ea507cd6c734bbe9f"
    na, nb = show(a, "nws.json")["records"], show(b, "nws.json")["records"]
    both = sorted({r["id"] for r in na} & {r["id"] for r in nb})[:2]
    keep = set(both) | {"KABQ.SV.W.0428.2026"}
    for sha, recs, tag, when in ((a, na, "a", "2026-11-01T23:50:24Z"), (b, nb, "b", "2026-11-02T06:42:24Z")):
        doc = {"commit": sha, "committed_at": when, "nws": [r for r in recs if r["id"] in keep],
               "health": show(sha, "health.json")}
        (OUT / f"nws_run_{tag}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                                 newline="\n")
        manifest["files"][f"nws_run_{tag}.json"] = f"data/nws.json (trimmed to {sorted(keep)}) and data/health.json at {sha}"

    # 2. A volcano alert raised: Great Sitkin (vnum 332010) went from ADVISORY to WATCH between two data commits.
    after = git("log", "-1", "--format=%H", "--before=2026-11-03T07:10:39Z", "origin/main", "--", "data").strip()
    before = git("log", "-1", "--format=%H", "--before=2026-11-03T07:10:38Z", f"{after}~1", "--", "data/usgs_volcano.json").strip()
    vols = {}
    for tag, sha in (("before", before), ("after", after)):
        recs = [r for r in show(sha, "usgs_volcano.json")["records"] if str(r.get("vnum")) == "332010"]
        vols[tag] = {"commit": sha, "records": recs, "health": show(sha, "health.json")}
    (OUT / "volcano_raised.json").write_text(json.dumps(vols, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                             newline="\n")
    manifest["files"]["volcano_raised.json"] = f"data/usgs_volcano.json (vnum 332010) and health at {before} and {after}"

    # 3. A failed source: NASA FIRMS failed on the run committed as c135e7f (12 Nov 17:18:38Z); the run before read it.
    bad = "c135e7f09"
    good = git("log", "-1", "--format=%H", f"{bad}~1", "--", "data/health.json").strip()
    (OUT / "health_firms_failed.json").write_text(json.dumps({"failed": show(bad, "health.json"), "ok": show(good, "health.json"),
                                                              "commits": [bad, good]}, indent=1) + "\n",
                                                  encoding="utf-8", newline="\n")
    manifest["files"]["health_firms_failed.json"] = f"data/health.json at {bad} (FIRMS failed) and {good} (read)"

    # 4. The catch-up: NWS's alerts issued since 13 Nov 00:00Z, recorded about 01:45Z 14 Nov, and the active list Elements
    #    held at its run committed as d98bd52 (14 Nov 01:36Z). Kept: the alerts of three events not active then and two
    #    that were, every message of each.
    since = json.loads(Path(nws_since_path).read_text(encoding="utf-8"))
    active = show("d98bd52", "nws.json")["records"]
    sys.path.insert(0, str(ROOT))
    from elements import weather
    parsed = weather.parse_nws({"features": since["features"]})
    act = {r["id"] for r in active}
    gone = [r["id"] for r in parsed if r["id"] not in act][:3]
    live = [r["id"] for r in parsed if r["id"] in act][:2]
    want = set(gone) | set(live)

    def key(f):
        one = weather.parse_nws({"features": [f]})
        return one[0]["id"] if one else None
    feats = [f for f in since["features"] if key(f) in want]
    (OUT / "nws_since.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats,
                                                    "pagination": since.get("pagination")}, ensure_ascii=False) + "\n",
                                        encoding="utf-8", newline="\n")
    (OUT / "nws_active_d98bd52.json").write_text(json.dumps({"records": [r for r in active if r["id"] in want]},
                                                            indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    manifest["files"]["nws_since.json"] = (f"NWS alerts API, start 2026-11-13T00:00:00Z, recorded about 01:45Z 14 Nov; "
                                           f"trimmed to the messages of {sorted(want)}")
    manifest["files"]["nws_active_d98bd52.json"] = "data/nws.json at d98bd52 (14 Nov 01:36Z), trimmed to the same events"
    manifest["catchup"] = {"not_active": gone, "active": live}
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
