"""The lead alert's ordering rule in site_src/app.js (ideas#260), run under node. Skipped when node is missing."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "site_src" / "app.js"
NODE = shutil.which("node")

HARNESS = """
var RANK = { green: 0, yellow: 1, orange: 2, red: 3 };
%s
var items = JSON.parse(process.argv[1]);
var alertOf = function (p) { return [p.c]; };
items.sort(function (x, y) { return leadOrder(x, y, alertOf); });
console.log(JSON.stringify(items.map(function (p) { return p.id; })));
"""


def order(items):
    src = APP.read_text(encoding="utf-8")
    block = re.search(r"// LEAD-BEGIN.*?// LEAD-END", src, re.S).group(0)
    out = subprocess.run([NODE, "-e", HARNESS % block, json.dumps(items)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def it(id_, c, at):
    return {"id": id_, "c": c, "data_as_of": at}


@unittest.skipUnless(NODE, "node is not installed")
class LeadTest(unittest.TestCase):
    def test_a_cyclone_leads_a_long_drought_on_the_same_rung(self):
        got = order([it("elements:gdacs:DR-1", "orange", "2026-11-23T00:00:00Z"),
                     it("elements:gdacs:TC-2", "orange", "2026-11-22T00:00:00Z")])
        self.assertEqual(got, ["elements:gdacs:TC-2", "elements:gdacs:DR-1"])

    def test_the_issuers_rung_still_comes_first(self):
        got = order([it("elements:gdacs:TC-2", "orange", "2026-11-23T00:00:00Z"),
                     it("elements:gdacs:DR-1", "red", "2026-11-01T00:00:00Z")])
        self.assertEqual(got[0], "elements:gdacs:DR-1")

    def test_a_tie_goes_to_the_newer_report_then_the_id(self):
        got = order([it("elements:gdacs:FL-1", "orange", "2026-11-22T00:00:00Z"),
                     it("elements:gdacs:TC-9", "orange", "2026-11-23T00:00:00Z"),
                     it("elements:gdacs:EQ-5", "orange", "2026-11-23T00:00:00Z")])
        self.assertEqual(got, ["elements:gdacs:EQ-5", "elements:gdacs:TC-9", "elements:gdacs:FL-1"])

    def test_no_alert_above_the_bottom_rung_sorts_and_stays_empty(self):
        self.assertEqual(order([]), [])
        self.assertEqual(order([it("a", "green", "2026-11-22T00:00:00Z"), it("b", "green", "2026-11-23T00:00:00Z")]),
                         ["b", "a"])


if __name__ == "__main__":
    unittest.main()
