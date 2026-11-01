"""Offline tests for Elements' USGS volcano lane. The fixture copies the live format of
https://volcanoes.usgs.gov/vsc/api/volcanoApi/elevated on 31 Oct 2026 (trimmed)."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, volcanoes  # noqa: E402
from tic_doctrine import contract, registers, vocab  # noqa: E402

NOW = datetime(2026, 10, 31, 22, 0, tzinfo=timezone.utc)
FETCHED = "2026-10-31T21:56:00Z"


def v(name, vnum, obs, alert, color, prev_alert, prev_color, lat, lon, sent="2026-10-31 18:26:13"):
    return {"noticeId": f"DOI-USGS-{obs.upper()}-x", "vName": name, "vnum": vnum, "volcanoCd": "x", "nvewsThreat": "High Threat",
            "lat": lat, "long": lon, "noticeSynopsis": f"{obs.upper()} {name} {color}/{alert} - Synopsis  text.",
            "obs": obs, "alertLevel": alert, "colorCode": color, "sentUtc": sent, "alertDate": sent,
            "alertLevelPrev": prev_alert, "colorCodePrev": prev_color, "codeChangeDate": sent,
            "noticeUrl": f"https://volcanoes.usgs.gov/hans-public/notice/DOI-USGS-{obs.upper()}-x"}


ELEVATED = [
    v("Kilauea", "332010", "hvo", "ADVISORY", "YELLOW", "WATCH", "ORANGE", 19.421, -155.287, "2026-10-31 20:36:30"),
    v("Great Sitkin", "311120", "avo", "WATCH", "ORANGE", "ADVISORY", "YELLOW", 52.076, -176.13),
    v("Shishaldin", "311360", "avo", "ADVISORY", "YELLOW", "NORMAL", "GREEN", 54.756, -163.97),
    v("Ahyi Seamount", "284141", "nmi", "ADVISORY", "YELLOW", "UNASSIGNED", "UNASSIGNED", 20.42, 145.03, "2026-10-29 23:23:07"),
]


def fetch_with(body):
    return lambda url, timeout=40, max_bytes=None: (body, None) if body is not None else (None, "HTTP 503")


class Parse(unittest.TestCase):
    def test_fields(self):
        r = {x["name"]: x for x in volcanoes.parse_usgs(ELEVATED)}
        k = r["Kilauea"]
        self.assertEqual((k["alert"], k["color"], k["prev_alert"], k["prev_color"]), ("ADVISORY", "YELLOW", "WATCH", "ORANGE"))
        self.assertEqual(k["sent"], "2026-10-31T20:36:30Z")
        self.assertEqual(k["observatory_name"], "Hawaiian Volcano Observatory")
        self.assertEqual(k["synopsis"], "HVO Kilauea YELLOW/ADVISORY - Synopsis text.")
        self.assertEqual(k["countries"], ["US"])
        self.assertEqual(r["Ahyi Seamount"]["countries"], ["MP"])   # at sea: the observatory's territory

    def test_change(self):
        r = {x["name"]: volcanoes.change(x) for x in volcanoes.parse_usgs(ELEVATED)}
        self.assertEqual(r, {"Kilauea": "lowered", "Great Sitkin": "raised", "Shishaldin": "raised", "Ahyi Seamount": "raised"})
        self.assertIsNone(volcanoes.change({"alert": "WATCH", "color": "ORANGE"}))

    def test_collect(self):
        self.assertEqual(volcanoes.collect_usgs(["old"], fetch_with(b"[]")), ([], None))   # nothing elevated is an answer
        got, err = volcanoes.collect_usgs(["old"], fetch_with(b""))
        self.assertEqual((got, err), (["old"], "empty answer"))
        got, err = volcanoes.collect_usgs(["old"], fetch_with(None))
        self.assertEqual((got, err), (["old"], "HTTP 503"))
        got, err = volcanoes.collect_usgs(None, fetch_with(json.dumps(ELEVATED).encode()))
        self.assertEqual(len(got), 4)


class Feed(unittest.TestCase):
    def build(self):
        d = {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}
        d["usgs_volcano"] = {"records": volcanoes.parse_usgs(ELEVATED), "fetched_at": FETCHED}
        return feed.build(d, NOW)

    def items(self, fc):
        return {f["properties"]["measures"]["name"]: f["properties"] for f in fc["features"]
                if f["properties"]["id"].startswith("elements:usgs-volcano:")}

    def test_items_pass_and_read_right(self):
        fc = self.build()
        self.assertEqual(fc["dropped"], [])
        regs = registers.ids(ROOT / "doctrine")
        for f in fc["features"]:
            self.assertEqual([m for _, sev, m in contract.check(f, regs) if sev == "error"], [], f["properties"]["id"])
        it = self.items(fc)
        self.assertEqual(it["Kilauea"]["title"], "Kilauea: USGS volcano alert Advisory, aviation code Yellow (lowered from Watch/Orange)")
        self.assertEqual(it["Great Sitkin"]["title"], "Great Sitkin: USGS volcano alert Watch, aviation code Orange (raised from Advisory/Yellow)")
        self.assertEqual(it["Ahyi Seamount"]["title"], "Ahyi Seamount: USGS volcano alert Advisory, aviation code Yellow (previously unassigned)")
        self.assertTrue(all(p["tier"] == "anomaly" and p["baseline_ref"]["id"] == "usgs-volcano-normal" for p in it.values()))
        self.assertEqual(it["Kilauea"]["id"], "elements:usgs-volcano:332010")

    def test_unassigned_alert_with_raised_colour(self):
        """A satellite-only volcano can have no ground-based alert level and still a raised aviation colour."""
        rec = volcanoes.parse_usgs([v("Gareloi", "311070", "avo", "UNASSIGNED", "YELLOW", "UNASSIGNED", "UNASSIGNED", 51.79, -178.79)])
        d = {k: {"records": [], "fetched_at": FETCHED} for k in ("usgs", "gdacs", "nhc", "cems")}
        d["usgs_volcano"] = {"records": rec, "fetched_at": FETCHED}
        fc = feed.build(d, NOW)
        self.assertEqual(fc["dropped"], [])
        p = self.items(fc)["Gareloi"]
        self.assertEqual(p["title"], "Gareloi: no ground-based alert level, aviation code Yellow (previously unassigned)")
        self.assertNotIn("response_stage", p)

    def test_response_stage_follows_the_kit(self):
        has = "usgs_volcano" in vocab.ladders()
        it = self.items(self.build())
        self.assertEqual("response_stage" in it["Kilauea"], has)
        ladders = dict(vocab.ladders())
        ladders.setdefault("usgs_volcano", {"values": {"normal": {}, "advisory": {}, "watch": {}, "warning": {}}})
        with patch.object(vocab, "ladders", return_value=ladders):
            fc = self.build()
            it = self.items(fc)
            self.assertEqual(it["Great Sitkin"]["response_stage"], "usgs_volcano:watch")
            self.assertEqual(fc["dropped"], [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
