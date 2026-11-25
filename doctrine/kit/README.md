# tic-doctrine

The shared doctrine kit for The Intelligence Company's programs (Noisefloor, Watchfloor, Context, Vigil, PropertyCast,
and the programs still to come). It turns each program's measurements into judgments that can be read the same way,
drawn on one map (COP) and scored (Verdict).

**What is in it**

| Path | What |
|---|---|
| `vocab/` | Reference vocabularies: ICD 203 likelihood with UK and Kent crosswalks; the confidence rubric; contract enums; JP 3-04 information aspects, PMESII-PT, ASCOPE, the competition continuum; CISA's 55 National Critical Functions with a published sector and lifeline crosswalk; FEMA's eight lifelines and status colours; response ladders (PAGER, USGS volcano alert levels, GDACS, Copernicus EMS, IFRC, EASA, State Department); Admiralty grades; ICD 203's nine tradecraft standards; actor roles and types, and source owners, for characterising entities and sides without friend-or-foe labels; the suite's shared zone keys (`zones.json`, Watchfloor's) |
| `schema/` | Feed contract v2 as JSON Schema |
| `geo/` | Country outlines and label points, US state outlines, and the sea gazetteer (`seas.json`, Natural Earth's named marine areas, public domain) |
| `python/tic_doctrine/` | Likelihood, confidence, contract checks, the tradecraft linter, register checks, source health, withholding counts, tips between programs, the history log (standard library only) |
| `js/tic-doctrine.js` | The same likelihood, confidence, lifeline, ladder and tip-matching logic for web pages (ES module, no dependencies) |
| `vocab/programs.json` | The suite registry: every program, its feed, and the datasets it owns |
| `docs/` | The contract, the reader's language key, the confidence rubric, the sources-and-withholding page, the history log format |
| `templates/doctrine/` | A program's registers: requirements, indicators and warning problems, assumptions, function map, sources, method |
| `tools/` | `sync.py` copies the kit into a program as `doctrine/kit/`; `build_js.py` and `build_schema.py` regenerate from `vocab/` |

**Use in a program**

```
python tools/sync.py ../<program>                # vendor the kit into <program>/doctrine/kit/
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
data at its address. Vis went live on 8 Nov 2026 (0.4.2), Blackout on 12 Nov 2026 (0.4.3); 0.4.4 (13 Nov 2026) adds Blackout's Cloudflare Radar data and its eleven provider status feeds to its entry. 0.4.5 (13 Nov 2026) adds Blackout's routing, power and context lanes (Radar BGP, the IAEA's Zaporizhzhya updates, ODIN, EIA-930, NASA Black Marble, Access Now STOP, Citizen Lab test lists) to its `owns`, and each new source's licence, as Blackout's `doctrine/sources.json` states it, to its `terms`. Headwind went live on 13 Nov 2026 (0.4.6): its `terms` are its feed's own licence line and its `owns` lists what it collects today. 0.4.7 (13 Nov 2026) adds Blackout's base rates for US state outages from ORNL's EAGLE-I outage history to its `owns`, and that history's licence (CC BY 4.0, as its figshare record states) to its `terms`. Orbit went live on 13 Nov 2026 (0.4.8), the same way: launches, scheduled launches, reentries and catalog changes from GCAT and Launch Library 2. Launch went live on 14 Nov 2026 (0.4.9): FAA space-operations TFRs and the scheduled launches that coincide with a closure area, beside its launch and reentry closure history.

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
in `countries`), so a consumer can tell a notice in Hawaii from one for all of the United States (15 Nov 2026);
`geo.subdivision_at(lat, lon)` and `geo.subdivisions_for_geometry(geom)` name the US state from Natural Earth's 1:10m
outlines (`geo/subdivisions.json`, built by `tools/build_subdivisions.py`; right to about 1 km at a state line).
0.5.8 (15 Nov 2026): the registry names Launch's history source as Launch's charted notices, not a person.
0.5.9 (16 Nov 2026): Relief is live (humanitarian response: IFRC GO appeals and WHO Disease Outbreak News, family
Society, prefix `RL-WP`) at relief.theintelligence.company; the planned `humanitarian` entry is renamed `relief`.
0.5.10 (16 Nov 2026): Launch's registry row names the history sources it ingests: NotamForChina (Apache-2.0),
Joey0609/notams (MIT), and Internet Archive copies of FAA TFRs and NGA warnings (US Government works), with GCAT.
0.5.11 (17 Nov 2026): Noisefloor's and Orbit's registry rows describe what each runs now: Noisefloor's space weather
(COSMIC-2 limb S4, ground ROTI), satellite-sensor interference lanes and sun outages; Orbit's TIP reentry predictions,
listed orbit changes, GEO region, new-payload paths and Secure World Foundation history, with their sources' terms.
Orbit's launch lines stay until Launch takes the schedule and ledger.
0.5.12 (18 Nov 2026): Blackout's registry row names its newest lanes: US ground stops from the FAA's ATCSCC, GitHub's
status feed, and outages the public and the press report (Bluesky post counts, GDELT headline counts), with each
source's terms word for word from Blackout's source register.
0.5.13 (18 Nov 2026): `history --reading-key PROPERTY` (opt-in): a move of that property is a `changed` line too,
with its value before in `was`, so a program whose ids stay the same across readings of a series (Headwind, with
`data_as_of`) logs every reading without reporting the one before as ended. Programs that do not pass it see no
change.

**0.6.0 (18 Nov 2026): feed contract revision 2.1.** Step 2 of the feed-contract migration (the suite's decisions D1 to D8,
18 Nov 2026). Additive: the contract string stays `tic-feed/2`, every new field is optional, and every feed that
passed 0.5.12 passes 0.6.0 with the same errors (checked on the 16 feeds in the registry, COP's among them, read
live on 18 Nov 2026).
- New optional item fields: `last_change`, `last_change_at`, `event_start`, `event_end`, `event_time_precision`,
  `subject_id`, `signal`, `sea_areas`, `place_basis`, `baseline_ref.flag_rate`, `sources[].lane`. Header:
  `contract_rev` (`"2.1"`), `kit`, and a documented `health` member (one key set; states fresh, late, stale, failing,
  never, up). Tightened meanings of `data_as_of`, `countries` (by overlap) and tier `anomaly` (D5: own history, 5%
  flag-rate cap, 72-hour hold). Vocabulary in `vocab/enums.json` 1.1; schema rebuilt, with the header under `$defs`.
- The linter checks each new field's shape when present (an error) and counts its absence per feed (a warning,
  never a failed build), and ends with a coverage line per field. A feed that states `contract_rev: "2.1"` is held to
  the health shape and the tightened `data_as_of` as errors; otherwise they are warnings.
- `geo.countries_overlapping()` (countries by overlap) beside the vertex-based `countries_for_geometry()`;
  `geo.sea_areas_for_geometry()`, `sea_at()`, `sea_name()` and `sea_slugs()` on the new gazetteer `geo/seas.json`:
  291 named areas from Natural Earth 1:10m marine areas, release v5.1.2 (public domain), built by
  `tools/build_seas.py`. Natural Earth has no separate Strait of Hormuz and no canals.
- History keys on `subject_id` when present, on `id` otherwise; lines carry `subject_id`; the state records `since`
  and when each subject last moved. `history --fill-last-change` (and `fill_last_change()`) fills `last_change` from
  the log for programs with no better knowledge.
- `contract.event_interval()` and the browser module's `eventInterval()` give an item's exact event interval;
  `seaName()` names a sea area; `health.feed_health()` turns a source-health report into header entries.
- New worked example `tests/fixtures/good-2.1.geojson`: the four example items with every 2.1 field.

**0.6.1 (18 Nov 2026): the shared zone list (D4).** `vocab/zones.json`: Watchfloor's 16 zone keys with names, ISO
countries and map points, and its one retired key (`17_Horn_of_Africa`, into `18_Ethiopia_Eritrea` and
`19_Somalia`), built by `tools/build_zones.py` from Watchfloor's `catalog/entities.json` (catalog 2026-10-27.1,
more-context `6bedddb`) and checked against Watchfloor's live feed. A `subject_id` of kind `zone` naming a key not in
the list, or a retired one, is a warning. `vocab.zones()`, `retired_zones()`, `zone()`; JS `zoneName()`. No feed
sends zone subjects yet, so no feed's lint changes.

**0.6.2 (18 Nov 2026): corroboration (D11) and four fixes from the 15 Nov kit review.** Additive: no feed's lint
gains an error (checked on the 16 registry feeds as read on 18 Nov 2026).
- **`corroboration` (D11):** an optional member for event items, "reported, then corroborated". The linter checks its
  shape and rules when present, and coverage counts it. The vocabulary is `corroboration_state` and
  `corroboration_basis` in `vocab/enums.json` 1.2.
- **M1, language key:** the kit repo is public, so `language_key` should be its page
  (`contract.LANGUAGE_KEY_URL`). A vendored copy draws a warning. Five feeds point at copies today: Context, COP,
  Noisefloor, Vigil and Watchfloor.
- **M4, Admiralty credibility 1:** a grade of 1 on an item with one independence group draws a warning, "grade it 2
  at most". Today that is 959 items on Cordon, 195 on Elements and 105 on Headwind.
- **M5, linter labels:** each row now reads "the fields it needs". The header says the check is structural, and
  standards 4, 7 and 8 print `n/a` when the files hold no judgments, updates or forecasts to check.
- **G3, confidence:** `confidence.method_scored(scores, program)` reads Verdict's `scores.json`, so a program with a
  scored record (Verdict's `skill_min_n`, 30) can reach High. No program has one yet.
- The fixtures link the public key; the 2.1 example's KEV item is graded A2 and corroborated by its issuer, and the
  strike is a reported party claim.

**0.6.4 (19 Nov 2026): code licences in the program register.** `vocab/programs.json` `terms` now say "code GNU
AGPL-3.0" for Blackout, Cordon, Elements, Headwind and Relief, which are AGPL-3.0 since 19 Nov 2026 (they read "code
MIT"). Blackout's feed takes its licence line from here, so it changes at Blackout's next kit sync. No code change.

**0.6.3 (18 Nov 2026): `history` takes the feed's own time.** Without `--now`, the run's time is the feed's
`generated_at` (the wall clock when the feed has none, or when it is later than the clock), so `first_seen` and a
filled `last_change_at` are never later than the items' `published_at`. Before, the step ran seconds after the build
and stamped the wall clock, and the contract check "last_change_at is later than published_at" failed: it stopped
every Blackout deploy on 18 Nov 2026 from 22:14 UTC until Blackout passed `--now` (PR #8). `--now` still wins.
`history.run_time(feed)`.

**0.6.4 (18 Nov 2026): Orbit's registry row names the GEO page.** `owns` adds the GEO page (globe, rendezvous and
proximity pairs, callouts and the belt board), which moved from Noisefloor on 18 Nov 2026; Noisefloor's row already
named no GEO lane. Registry text only.

**0.6.5 (21 Nov 2026): Blackout's registry row names NetBlocks and the trend series.** `owns` adds NetBlocks' reports
(from its public Bluesky posts: times, links, parsed fields and short excerpts) and the daily outage series per country
(IODA, Cloudflare Radar and NetBlocks, for 7, 14 and 30-day trends). `terms` adds NetBlocks' terms word for word from
Blackout's doctrine/sources.json: NetBlocks publishes no reuse licence (all rights reserved), so Blackout never
republishes a post's full text. Registry text only.

**0.6.6 (21 Nov 2026): Blackout's registry row names internet-user exposure.** `owns` adds internet users per
country (ITU's share of people online times the population, via the World Bank's WDI) as an upper bound on exposure
beside each country outage and in the trend series, never users affected. `terms` adds the ITU/World Bank terms word for
word from Blackout's doctrine/sources.json. Registry text only.

**0.6.7 (20 Nov 2026): Blackout's registry row names Viasat MSS.** `owns` adds Viasat MSS to the providers' own
status feeds (Viasat's page for its mobile satellite services, the one satellite operator beyond Starlink found with a
readable feed). `terms` adds its licence word for word from Blackout's doctrine/sources.json. Registry text only.

**0.6.8 (20 Nov 2026): Blackout's registry row names satellite-network traffic drops.** `owns` adds satellite
networks' traffic drops against their own weekday-matched normal (Blackout's BO-IND-21, read from Cloudflare Radar
traffic by network). `terms` already credits Cloudflare Radar data CC BY-NC 4.0. Registry text only.

**0.6.9 (20 Nov 2026): Relief's registry row matches relief-0.3.** `status_note` and `owns` name the HDX HAPI and ReliefWeb lanes (IPC stays planned); `terms` adds the HAPI and ReliefWeb terms. Registry text only.

**0.6.10 (21 Nov 2026): Wake's licence in the program register.** `terms` now says "Wake code GNU AGPL-3.0" (it read "code MIT"), matching Wake's LICENSE. Registry text only.

**0.6.11 (24 Nov 2026): neutral attributions.** Dated notes in the schema, vocabularies, templates, docs and tools no longer name a person: each keeps its date ("(15 Nov 2026)"), and a rule or decision is "the suite's". Wording only; no field, value or rule changes.

**0.6.12 (24 Nov 2026): zone list rebuilt from Watchfloor's catalog at 3ab3a28.** The retired zone `17_Horn_of_Africa` keeps its reason without a name. Text only; keys, countries and map points unchanged.

**Tests:** `python tests/test_kit.py`, `python tests/test_history.py` and `node tests/test_js.mjs`.

**Claims.** The methods are aligned with the principles of ICD 203, 206 and 208. Those directives bind US Intelligence
Community elements only; this is an independent, non-commercial research effort, so it never claims compliance. Only
released doctrine is cited.

Code: MIT. Vocabulary files restate public US government and allied publications, credited in each file.
