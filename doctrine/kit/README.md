# tic-doctrine

The shared doctrine kit for The Intelligence Company's programs (Noisefloor, Watchfloor, Context, Vigil, PropertyCast,
and the programs still to come). It turns each program's measurements into judgments that can be read the same way,
drawn on one map (COP) and scored (Verdict).

**What is in it**

| Path | What |
|---|---|
| `vocab/` | Reference vocabularies: ICD 203 likelihood with UK and Kent crosswalks; the confidence rubric; contract enums; JP 3-04 information aspects, PMESII-PT, ASCOPE, the competition continuum; CISA's 55 National Critical Functions with a published sector and lifeline crosswalk; FEMA's eight lifelines and status colours; response ladders (PAGER, USGS volcano alert levels, GDACS, Copernicus EMS, IFRC, EASA, State Department); Admiralty grades; ICD 203's nine tradecraft standards; actor roles and types, and source owners, for characterising entities and sides without friend-or-foe labels |
| `schema/` | Feed contract v2 as JSON Schema |
| `python/tic_doctrine/` | Likelihood, confidence, contract checks, the tradecraft linter, register checks, source health, withholding counts, tips between programs, the history log (standard library only) |
| `js/tic-doctrine.js` | The same likelihood, confidence, lifeline, ladder and tip-matching logic for web pages (ES module, no dependencies) |
| `vocab/programs.json` | The suite registry: every program, its feed, and the datasets it owns |
| `docs/` | The contract, the reader's language key, the confidence rubric, the sources-and-withholding page, the history log format |
| `templates/doctrine/` | A program's registers: requirements, indicators and warning problems, assumptions, function map, sources, method |
| `tools/` | `sync.py` copies the kit into a program as `doctrine/kit/`; `build_js.py` and `build_schema.py` regenerate from `vocab/` |

**Use in a program**

```
python tools/sync.py [local path]<program>            # vendor the kit into <program>/doctrine/kit/
python doctrine/kit/tic.py lint <feed>.geojson --doctrine doctrine
python doctrine/kit/tic.py registers doctrine
python doctrine/kit/tic.py health doctrine/sources.json --out doctrine/health.json
python doctrine/kit/tic.py history site/data/feed.geojson --dir history --ended site/data/ended.geojson
```

**Tips between programs (0.4.0, 1 Nov 2026).** Each dataset is collected once, by the program that owns it
(`vocab/programs.json`); the others read the owner's findings instead of collecting them again. A program lists what it
wants in `doctrine/interests.json` (areas as country sets, then interests: which programs, tiers, response stages,
title words or measure tests). `tips()` matches those interests against the bus, COP's merged snapshot of every live
feed, or against one feed; `cite()` turns a tip into a source entry that carries the upstream lineage, so the
two-source rule and convergence count each original source once; `diff()` finds new, changed and ended tips between
runs. A stale producer gives stale tips, drawn grey.

**Geometry (0.4.1).** Items placed only by shape, such as navigational warnings at sea, match an area through the
countries their points fall in, or through `boxes` in `interests.json` (`[west, south, east, north]` per area, one box
or a list). Matching uses bounding boxes, so a very large warning area can land in two neighbouring areas, and boxes do
not cross the 180° meridian. A registry entry stays `planned` (with a `status_note`) until its program publishes real
data at its address. Vis went live on 8 Nov 2026 (0.4.2), Blackout on 12 Nov 2026 (0.4.3); 0.4.4 (13 Nov 2026) adds Blackout's Cloudflare Radar data and its eleven provider status feeds to its entry. 0.4.5 (13 Nov 2026) adds Blackout's routing, power and context lanes (Radar BGP, the IAEA's Zaporizhzhya updates, ODIN, EIA-930, NASA Black Marble, Access Now STOP, Citizen Lab test lists) to its `owns`, and each new source's licence, as Blackout's `doctrine/sources.json` states it, to its `terms`. Headwind went live on 13 Nov 2026 (0.4.6): its `terms` are its feed's own licence line and its `owns` lists what it collects today. 0.4.7 (13 Nov 2026) adds Blackout's base rates for US state outages from ORNL's EAGLE-I outage history to its `owns`, and that history's licence (CC BY 4.0, as its figshare record states) to its `terms`. Orbit went live on 13 Nov 2026 (0.4.8), the same way: launches, scheduled launches, reentries and catalog changes from GCAT and Launch Library 2. Launch went live on 14 Nov 2026 (0.4.9): FAA space-operations TFRs and the scheduled launches that coincide with a closure area, beside Tom's launch closure history.

```
python doctrine/kit/tic.py tips doctrine                  # against the bus
python doctrine/kit/tic.py tips doctrine --feed <url>     # against one program's feed
```

**History (0.5.0, 14 Nov 2026).** A feed carries what is active now; `history` keeps what was. Each run compares the
feed just built with the last run and logs one line per item that is new, changed (tier or response stage) or ended,
with the full item, to `history/log/YYYY/MM/DD.jsonl` (format `tic-history/1`, first written for Elements). An item
ends only when its source was read well on that run. The program serves the last 7 days of ended items beside its
feed as `data/ended.geojson`. Format and adoption steps: `docs/history-log.md`. 0.5.1 (14 Nov 2026): a health entry's own
`state`, when it gives one, must be fresh, late or up for its items to end (Cordon withholds a stale source's items).
0.5.2 (14 Nov 2026): Headwind's entry adds the EU and UK sanctions lists to its `owns`, and their licences and USGS's
(CC0 1.0) to its `terms`.
0.5.3 (14 Nov 2026): Undertow is live (influence operations, family Information, prefix `UT-WP`), with its
events and STIX files in `extra`.
0.5.4 (15 Nov 2026): Wake's entry, still planned, describes its rebuilt PortWatch lane: status note, terms, `owns`,
and freshness windows of 240 and 408 hours on its items' `data_as_of`, because PortWatch publishes weekly with a
lag of 2 to 9 days (Wake's own source health: fresh to 10 days, late to 17).
0.5.5 (15 Nov 2026): Wake is live (vessel transits through 28 chokepoints, family Maritime, prefix `WK-WP`) at wake.theintelligence.company,
read and deployed by hand once a week until the IMF permits automated pulls.
0.5.6 (15 Nov 2026): optional `data_as_of_precision` (`day` or `month`) for sources that give no time, with the
linter's midnight-UTC check and `asOfDateLabel()` in the browser module, so a date-only item is shown as a date and
not as the evening before; Undertow's `terms` now say what it quotes with credit (Meta, OpenAI, TikTok, EEAS).
0.5.7 (15 Nov 2026): optional item field `subdivisions` (ISO 3166-2 codes such as `US-HI`, each one's country also
in `countries`), so a consumer can tell a notice in Hawaii from one for all of the United States (Tom, 15 Nov 2026);
`geo.subdivision_at(lat, lon)` and `geo.subdivisions_for_geometry(geom)` name the US state from Natural Earth's 1:10m
outlines (`geo/subdivisions.json`, built by `tools/build_subdivisions.py`; right to about 1 km at a state line).
0.5.8 (15 Nov 2026): the registry names Launch's history source as Launch's charted notices, not a person.

**Tests:** `python tests/test_kit.py`, `python tests/test_history.py` and `node tests/test_js.mjs`.

**Claims.** The methods are aligned with the principles of ICD 203, 206 and 208. Those directives bind US Intelligence
Community elements only; this is an independent, non-commercial research effort, so it never claims compliance. Only
released doctrine is cited.

Code: MIT. Vocabulary files restate public US government and allied publications, credited in each file.
