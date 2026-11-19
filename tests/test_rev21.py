"""Offline tests for Elements' feed contract revision 2.1 fields (elements/rev21.py, kit 0.6.4, 19 Nov 2026)."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elements import feed, rev21  # noqa: E402
from elements.weather import chain_key  # noqa: E402
from tic_doctrine import contract  # noqa: E402

NOW = datetime(2026, 11, 19, 21, 0, tzinfo=timezone.utc)
F = "2026-11-19T20:55:00Z"


def item(iid, measures=None, geometry=None, **props):
    p = {**feed._base(F), "id": iid, "title": "t", "tier": "routine", "data_as_of": F, "countries": [],
         "requirement_ids": ["EL-PIR-1"], "sources": [{**feed.SRC["usgs"], "accessed_at": F}], "measures": measures or {}}
    p.update(props)
    return {"type": "Feature", "geometry": geometry, "properties": p}


class ChainKey(unittest.TestCase):
    def test_no_references_is_the_message_itself(self):
        self.assertEqual(chain_key({"id": "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.abc123.003.1"}),
                         "abc123.003.1")

    def test_update_takes_the_first_message_of_its_chain(self):
        p = {"id": "urn:oid:2.49.0.1.840.0.new.002.1",
             "references": [{"identifier": "urn:oid:2.49.0.1.840.0.second.002.1", "sent": "2026-11-19T12:00:00-06:00"},
                            {"identifier": "urn:oid:2.49.0.1.840.0.first.001.1", "sent": "2026-11-19T10:00:00-06:00"}]}
        self.assertEqual(chain_key(p), "first.001.1")

    def test_two_alerts_keep_two_keys(self):
        # The key before 19 Nov was "1" for every alert without VTEC.
        a = chain_key({"id": "urn:oid:2.49.0.1.840.0.aaa.001.1"})
        b = chain_key({"id": "urn:oid:2.49.0.1.840.0.bbb.001.1"})
        self.assertNotEqual(a, b)


class Decisions(unittest.TestCase):
    def test_drought_moves_past_one_point(self):
        self.assertEqual(rev21.usdm_change({"change_d2": 1.4}), "raised")
        self.assertEqual(rev21.usdm_change({"change_d2": -2.0}), "lowered")
        self.assertEqual(rev21.usdm_change({"change_d2": -0.2}), "none")
        self.assertEqual(rev21.usdm_change({"change_d2": None}), "none")

    def test_corroboration_times_in_order(self):
        q = {"time": "2026-11-19T18:41:19Z", "updated": "2026-11-19T19:00:00Z"}
        c = rev21.corroboration(q, {"updated": "2026-11-19T20:49:28Z"})
        self.assertEqual((c["state"], c["basis"], c["origins"]), ("corroborated", "origins", 2))
        self.assertEqual(c["first_reported_at"], "2026-11-19T18:41:19Z")
        self.assertEqual(c["corroborated_at"], "2026-11-19T20:49:28Z")
        errs = []
        contract.check_corroboration(c, contract.parse_utc(F), lambda std, msg: errs.append(msg))
        self.assertEqual(errs, [])

    def test_one_independence_group_is_credibility_two(self):
        x = item("elements:usgs:a")
        rev21.regrade(x["properties"])
        self.assertEqual(x["properties"]["sources"][0]["grade"], "A2")
        y = item("elements:usgs:b")
        y["properties"]["sources"].append({**feed.SRC["emsc"], "accessed_at": F})
        rev21.regrade(y["properties"])
        self.assertEqual([s["grade"] for s in y["properties"]["sources"]], ["A1", "A1"])


class Finish(unittest.TestCase):
    def test_lane_fields(self):
        feats = [
            item("elements:nws:KLOX.FF.W.0024.2026", {"onset": "2026-11-19T16:05:00Z", "ends": "2026-11-19T20:00:00Z",
                                                      "severity": "Severe"}, countries=["US"],
                 geometry={"type": "Point", "coordinates": [-118.2, 34.1]}),
            item("elements:usdm:us", {"map_date": "2026-11-17", "valid_end": "2026-11-23", "d2": 17.42, "change_d2": 1.5},
                 precision_class="country", countries=["US"], geometry={"type": "Point", "coordinates": [-98.5, 39.8]}),
            item("elements:usgs:offshore", geometry={"type": "Point", "coordinates": [-172.0, -16.0]},
                 data_as_of="2026-11-19T18:00:00Z"),
            item("elements:meteoalarm:de:in-force", {"warnings": 3}, countries=["DE"], precision_class="country",
                 geometry={"type": "Point", "coordinates": [10.4, 51.1]}),
        ]
        rev21.finish(feats)
        nws, usdm, quake, count = (f["properties"] for f in feats)
        self.assertEqual((nws["event_start"], nws["event_end"]), ("2026-11-19T16:05:00Z", "2026-11-19T20:00:00Z"))
        self.assertEqual(nws["signal"]["value"], 3)
        self.assertEqual(nws["place_basis"], "location")
        self.assertEqual((usdm["event_start"], usdm["event_time_precision"]), ("2026-11-17T00:00:00Z", "day"))
        self.assertEqual((usdm["last_change"], usdm["last_change_at"]), ("raised", "2026-11-17T00:00:00Z"))
        self.assertEqual(usdm["sea_areas"], [])
        self.assertTrue(quake["sea_areas"])               # in the South Pacific
        self.assertEqual(quake["event_start"], "2026-11-19T18:00:00Z")
        self.assertNotIn("event_start", count)            # a count of warnings is no one event
        for f in feats:
            p = f["properties"]
            self.assertEqual(p["subject_id"], p["id"])
            self.assertEqual([m for _, sev, m in contract.check(f, None, "2.1") if sev == "error"], [], p["id"])

    def test_filled_change_never_after_publication(self):
        x = item("elements:usgs:late")
        state = {"open": {"elements:usgs:late": {"first_seen": "2026-11-19T20:58:00Z", "item": x,
                                                 "last_change": "new", "last_change_at": "2026-11-19T20:58:00Z"}}}
        rev21.finish([x], state, since="2026-11-13T00:00:00Z")
        p = x["properties"]
        self.assertEqual(p["last_change"], "new")
        self.assertEqual(p["last_change_at"], F)          # the history run came after the fetch: clamped

    def test_health_states(self):
        h = rev21.health_states({
            "a": {"last_ok": F, "checked_at": F, "failures": 0},
            "b": {"last_ok": "2026-11-19T18:00:00Z", "checked_at": F, "last_error": F, "failures": 1},
            "c": {"last_ok": "2026-11-15T00:00:00Z", "checked_at": F, "last_error": F, "failures": 30},
            "d": {"last_ok": None, "checked_at": F, "last_error": F, "failures": 2}}, {"a": F}, NOW)
        self.assertEqual({k: v["state"] for k, v in h.items()}, {"a": "fresh", "b": "failing", "c": "stale", "d": "never"})
        self.assertEqual(h["a"]["data_as_of"], F)
        self.assertEqual(contract.check_health(h, strict=True), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
