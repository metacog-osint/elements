# Feed contract v2 (`tic-feed/2`)

Every program publishes its items in this shape: GeoJSON first (a FeatureCollection whose features carry these fields
in `properties`, with `geometry: null` for items with no place), or JSON lines of flat items. The machine-readable form
is [`schema/feed-item-v2.schema.json`](../schema/feed-item-v2.schema.json); the tradecraft linter
(`python tic.py lint`) checks everything below, including the conditional rules. A worked example is
[`tests/fixtures/good.geojson`](../tests/fixtures/good.geojson).

**Revision 2.1 (kit 0.6.0, 18 Nov 2026).** An additive revision: the contract string stays `tic-feed/2`, every new
field is optional, and the linter notes a missing one as a warning that never fails a build (Tom's decisions D1 to
D8, 18 Nov 2026). Revision 2.2 will make each field compulsory once every feed sends it. The new fields are in
[Revision 2.1 fields](#revision-21-fields) below; a worked example with all of them is
[`tests/fixtures/good-2.1.geojson`](../tests/fixtures/good-2.1.geojson).

## Feed header (FeatureCollection)

`contract`, `program`, `generated_at`, `licence`, `attribution`, and `language_key` (a link to the
[language key](language-key.md)). From kit 0.6.2 the linter warns unless `language_key` is the kit's own public page,
`https://github.com/metacog-osint/tic-doctrine/blob/main/docs/language-key.md`: a copy vendored into a program's repo
goes stale with that program's kit. Optional: `perspectives`, a map from each `sources[].perspective` id to its label
(`{"russian_state": "Russian state and Kremlin-aligned media"}`), so readers and COP can name each side's media.

Revision 2.1 adds three header members, each optional (the linter notes their absence):

| Member | Meaning |
|---|---|
| `contract_rev` | `"2.1"`: the revision the feed meets. A feed that states it is held to the 2.1 shape of `health` and the tightened `data_as_of` as errors; without it those are warnings |
| `kit` | The vendored kit version, such as `"0.6.0"`, so drift can be seen from outside |
| `health` | One entry per source lane the program reads, keyed by lane id, written on every run (below) |

**`health`.** "Read and found nothing" and "not read" are different facts, and the feed says which. Each entry:

| Key | Meaning |
|---|---|
| `state` | One of `fresh`, `late`, `stale`, `failing`, `never`, `up` ([`vocab/enums.json`](../vocab/enums.json) `health_state`). Not `failed`: that is `failing` |
| `checked_at` | When this run checked the lane (UTC) |
| `last_ok` | The last time it was read well (UTC), or `null` if never |
| `last_error` | The last error, or `null` |
| `failures` | Failed checks in a row, 0 when it read well |
| `data_as_of` | The newest data that source holds (UTC, ending in Z; a date-only source writes midnight UTC) |
| `detail` | One line, such as "24 of 24 HS codes with imports, newest month 2026-09" |

Other keys are allowed. A lane counts as read when `last_ok` equals `checked_at` and its state is fresh, late or
up, the rule the history log applies. Every item's first source id is a lane key, or names its lane in
`sources[].lane`. A lane with no items today is still listed. `health.feed_health()` builds the entries from the
kit's source-health report.

## Every item

| Field | Meaning | Basis |
|---|---|---|
| `contract`, `id`, `program`, `title` | `tic-feed/2`; stable id; program; what happened, one line | |
| `kind` | observation, assessment or forecast | ICD 203 standard 3 |
| `tier` | routine or anomaly (measured), warning (judged) | Grabo; NATO indicators versus indications |
| `status`, `msg_type`, `supersedes`, `valid_until` | actual/exercise/test/draft; new/update/cancel/error; the item replaced; expiry | CAP 1.2 |
| `human_review` | none, sampled or full | ICD 505 labelling idea |
| `us_person_data` | none, organizations or individuals: a label, so a consumer bound by US-person rules (a government user, for example) can filter; never a reason to leave data out | suite rule (Tom, 30 Oct 2026) |
| `status_class` | assessed, reported or claimed (claims draw hollow and move nothing alone) | Watchfloor two-source rule |
| `data_as_of`, `published_at` | when it was true; when we published it (UTC, ending in Z). From revision 2.1, `data_as_of` is the newest observation or source statement the item rests on (for a notice, its issue or last-edit time): never later than `published_at`, and the build time only when the observation was made at build time | ICD 206 |
| `countries` | ISO 3166-1 alpha-2 codes, `[]` for none. From revision 2.1, by overlap: every country the item's true footprint covers, not only those under its vertices (`geo.countries_overlapping()`); `place_basis` says why they are named | |
| `subdivisions` | optional: ISO 3166-2 codes of the states or provinces the item is in (`["US-HI"]`), each one's country also in `countries`; leave it out when not known. A consumer matching by place should prefer it to `countries`, so a notice in Hawaii is not read as one for all of the United States | suite rule (Tom, 15 Nov 2026) |
| `coverage_fraction` | share of expected observations received | Primer quality-of-information check |
| `method_version` | the method that made the item | |
| `sources[]` | `id`, `publisher`, `author`, `title`, `outlet`, `source_type`, `url`, `published_at`, `accessed_at`, `licence`, `descriptor` (credibility, reliability, provenance, collector or tool), `grade` (Admiralty, e.g. B2), `lineage_id`, `independence_group`; optional `owner` (state, public, private, intergovernmental, ngo, individual, unknown) and `perspective` (the program's source group, e.g. `russian_state`) | ICS 206-01 (2 Dec 2024) citation fields, without classification fields; Admiralty system; owner and perspective from Watchfloor's source catalog |
| `geometry` or `visual` | a place on the map, or `{type, url}` for a graphic | ICD 203 standard 9; visual-first rule |

Optional on every item: `summary`, `evidence_hash` (`sha256:...`), `archive_url`, `requirement_ids[]`,
`precision_class`, `product_category`, `data_as_of_precision`, `actors[]` (below), and the tags below.

`data_as_of_precision` is for a source that gives no time. With `day`, `data_as_of` is midnight UTC on that date;
with `month`, it is midnight UTC on the 1st. A page then shows the date ("30 Oct 2026") or the month ("June 2025"),
read in UTC, and never a time or a zone; the kit's `asOfDateLabel()` does this. Without the field, `data_as_of` is a
moment and is shown in the viewer's zone. Midnight UTC shown as a time reads as the evening before in the Americas
(Tom, 15 Nov 2026).

## Revision 2.1 fields

All optional at revision 2.1. When a field is present the linter checks its shape and a bad one is an error; when it
is absent the linter counts it (`rev 2.1: subject_id absent`, once per feed with the number of items) and the build
passes. The report ends with a coverage line, the count of items carrying each field: COP's migration dashboard.

| Field | Meaning | Type and rules |
|---|---|---|
| `last_change` | The most recent change in the state of the item's subject: `new` (first appeared), `raised`, `lowered` (its level moved on its own ladder or across its own threshold), `changed` (scope, place or wording, the level the same), `ended`, `none` (no change in the program's record: standing as long as the program has watched). State is `tier` and `response_stage`; a program may add its own level and says so on its method page | closed list (`vocab/enums.json`) |
| `last_change_at` | When that change happened, as the source dates it; where it gives none, the program's first reading in the new state | UTC ending in Z; required with every `last_change` but `none`; never after `published_at` |
| `event_start`, `event_end` | When what the item describes began and ended **in the world**, or is scheduled to. A measurement over a window: the window. A notice: when what it announces takes effect and stops, not when it was issued. A forecast: the period forecast. `event_end` only when the source says it ended or schedules its end | UTC ending in Z; `event_end` not before `event_start` |
| `event_time_precision` | `hour`, `day` or `month`, for a source that gives no finer time. Each time sits at the start of its period (on the hour, midnight UTC, midnight UTC on the 1st) and covers the whole period; `day` and `month` follow the date-only display rule of `data_as_of_precision` | closed list; needs an event time |
| `subject_id` | The thing the item is a reading of: a zone, a country series, a cell, an actor, a notice, an outage, a launch. No date or run stamp; the same on every reading of that subject by the program. The `id` itself where the id is stable; otherwise `program:kind:key` with ISO country keys (`headwind:fx:TRY`, `watchfloor:country:BH:violence`) | string, no spaces; equal to `id` or starting `<program>:` with three or more parts. A date in it is noted |
| `signal` | The one number the item's tier rests on: `name` (what is measured), `value`, `unit`, `expected` (the baseline's central value), `tail` (`high`, `low` or `both`), `baseline_n` (readings in the baseline), `exceedance` (the share of this subject's own baseline readings at least as extreme as this one; with `baseline_n` 28 the smallest is 1 in 29). COP computes the comparable rarity from it | object; `name` and a finite `value` required; numbers finite |
| `baseline_ref.flag_rate` | The share of baseline readings on which this subject was flagged | 0 to 1 |
| `sea_areas` | Slugs of the named seas, gulfs, straits and oceans the geometry overlaps, from the kit's gazetteer [`geo/seas.json`](../geo/seas.json) (Natural Earth 1:10m marine areas, public domain); `[]` on land. `geo.sea_areas_for_geometry()` computes it | list of gazetteer slugs |
| `place_basis` | Why the item names these countries: `location` (it is or happened there), `subject` (it is about that country: an advisory, a currency), `named` (a party is named: a victim's country, a network's home; a join by place skips it), `zone` (the program's own multi-country zone, one place) | closed list |
| `sources[].lane` | The source lane's key in the header's `health`, when it is not the source id | non-empty string |

Rules that come with them:

- **Geometry is the true footprint**, and `precision_class` becomes compulsory at 2.2 (its absence is noted now). An
  area item is drawn as its area; `precision_class: area` on a point is noted.
- **The grid cell is COP's**, computed at ingest. It is not a contract field.
- **The gazetteer** is Natural Earth's 291 named marine areas (release v5.1.2), rounded to about 1 km. They do not
  overlap, so a point at sea is in one area at most. Natural Earth has no separate Strait of Hormuz (it lies in the
  Persian Gulf and the Gulf of Oman), no canals (they are land), and no unnamed internal waters. Country outlines
  stay thinned to about 5 km, so a footprint that only grazes a coast can miss that country by overlap too (the
  Gulf of Finland box in the fixture reaches the Finnish coast at 60.5°N, and the outlines do not).
- **The event interval** has one rule, in `contract.event_interval()` (Python) and `eventInterval()` (browser
  module): `event_start` to `event_end`; with no end, `event_start` to `data_as_of` (ongoing as of the last look),
  or the moment `event_start` alone when it is later than `data_as_of` (scheduled); a precision widens each end to
  its whole hour, day or month.
- **`last_change` from the history log.** A program with no better knowledge runs
  `tic.py history ... --fill-last-change` ([history log](history-log.md)). A program that knows more (an issuer's
  own "raised", a notice's issue time) states the fields itself, and they are kept.

**Tier `anomaly` at revision 2.1** (D5). An item is an anomaly only when all of these hold:

1. It is an observation of a subject with a `subject_id`, and that subject has not ended.
2. It departs from that subject's own history, in one of two ways:
   - *A series* (a count, rate, price or index read every cycle): `signal.value` is beyond a threshold set on the
     subject's own rolling baseline, and the subject was flagged on no more than **5%** of its baseline readings
     (`baseline_ref.flag_rate`).
   - *An event or a notice* (it exists or not; it sits on an issuer's ladder): `last_change` is `new` or `raised`,
     the level is at or above the threshold the program states for that ladder, and `last_change_at` is within the
     program's hold, **72 hours** unless the program states another. After the hold it is routine, and
     `last_change_at` still says when it began.
3. The numbers that show it are in the item.

**Corroboration (kit 0.6.2, D11): "reported, then corroborated".** An optional `corroboration` member on items
that report an event (a strike, an attack at sea, an alert), never on measurements:

| Member | Meaning |
|---|---|
| `state` | `reported` until the rule is met, then `corroborated`. It never moves back: a retraction is a new item or a `last_change` |
| `basis` | `origins` or `official`; null while reported |
| `origins` | Independent origins counted so far, at least 1. Wire copies and texts with 80% word overlap are one origin; one government's outlets are one origin |
| `official` | The issuer's source id when `basis` is `official` (`ukmto`, `usembassy-bh`), else null. An issuer speaking about its own remit: UKMTO for incidents it logs, an embassy for its own alert, a ministry or armed force for its own government's actions and territory |
| `party_claim` | Optional, default false: every origin so far is a party claiming its own action or an adversary's loss. Such an item stays reported until an origin outside the party reports it |
| `first_reported_at`, `corroborated_at` | When the first origin appeared; when the rule was met (null while reported) |
| `rule` | The rule's id and text, printed (`corroborate-1: two independent origins, or one official source within its remit`) |

The linter checks the shape and these rules as errors when the member is present:
- `corroborated` on origins needs `origins` of 2 or more; on official it needs `official`.
- A party claim counts as corroborated only with 2 or more origins.
- `corroborated_at` is not before `first_reported_at` and not after `published_at`.

No field yet marks an item as an event report, so the member's absence is not noted. It is counted in the coverage
line. Wake and Cordon adopt it first (official issuers, no counting), then Watchfloor's feed stories.

**Admiralty credibility 1 (kit 0.6.2).** Credibility 1 is "confirmed by other sources" (`vocab/grading.json`). An
item that grades a source 1 while all its sources sit in one independence group is warned to grade it 2 at most:
a lone State Department advisory is a reliable source (A) that nothing has confirmed (A2). A warning, not an error.

**Zones (kit 0.6.1, D4).** A subject of kind `zone` (`watchfloor:zone:11_Iran_Red_Sea`, `context:zone:...`,
`vis:zone:...`, a Vis station suffix such as `-UKOO` allowed) names a key in the shared zone list,
`vocab/zones.json`. Watchfloor owns the list (its `catalog/entities.json`); the kit copies it with
`tools/build_zones.py`, countries as ISO codes. A key not in the list, or one Watchfloor has retired
(`17_Horn_of_Africa`, split on 27 Oct 2026 into `18_Ethiopia_Eritrea` and `19_Somalia`), is a warning, never an
error. `vocab.zone(key)` and JS `zoneName(key)` read it.

A fixed line with no reference to the subject's past, a rung that has not moved, a product type, "the provider lists
it" and "issued recently" with no level do not qualify by themselves. Each program adopts the rule as its own method
version; until then the linter notes, as warnings, an anomaly whose event ended more than 72 hours before publication,
whose flag rate is over 5%, or which has no `signal` and no recent rise. A standing departure is not hidden: it reads
routine or anomaly by rule 2, and `last_change: none` or an old `last_change_at` marks it standing. Tier `warning` is
unchanged.

## Actors and sides (`actors[]`)

Who plays what part in the item, **as the cited sources describe it**. A role is never a judgment of friend or foe: no
value means friendly, hostile, enemy or adversary, and when COP draws an actor the frame is only ever *unknown* or
*neutral*. A side is named the way the sources name it ("Russia", "Ukraine"). Vocabulary:
[`vocab/actors.json`](../vocab/actors.json).

| Field | Meaning |
|---|---|
| `name` | The actor, as the sources name it |
| `role` | party, supporter, responsible, affected, civilians, third_party or unknown (meanings below) |
| `actor_type` | optional: government, armed_forces, security_service, armed_group, criminal_group, political_group, company, intergovernmental, ngo, media, population, individual or unknown |
| `side` | the party, named as the sources name it: required for a party and for a supporter (the party it backs), optional for affected, civilians and unknown, never for a third party |
| `function` | what a third party does: mediator, monitor, observer, aid |
| `status_class` | how the characterisation is known: assessed, reported or claimed (a claim draws hollow) |
| `source_ids[]` | ids from this item's `sources[]` that the characterisation rests on |
| `country`, `designations[]`, `ref` | optional: ISO code; government designations `{by, label, source_id}` quoted as published (a sanctions listing, a terrorist designation); a stable id such as `wikidata:Q12345` |

| Role | Meaning | Frame |
|---|---|---|
| party | A party to the conflict or dispute; `side` names which | unknown |
| supporter | Backs a party (troops, arms, money, basing, diplomacy) without being one; `side` names the party it backs | unknown |
| responsible | The actor the sources hold responsible for the action, or that claims it | unknown |
| affected | The organization, group or place hit: a ransomware victim, an airport losing GPS, a struck port | neutral |
| civilians | Non-combatants, as a population or group, never named individuals | neutral |
| third_party | Involved on no side: mediator, monitor, observer, aid or emergency responder | neutral |
| unknown | Named, but its part is not established | unknown |

Rules the linter enforces:
- A party or supporter needs `side`. A side containing a friend-or-foe word ("enemy forces", "hostile") fails.
- `responsible` needs `source_ids`. If the suite makes the attribution itself (`status_class: assessed`), the item
  must be a judgment, with likelihood, confidence and alternatives. A group claiming an attack is `claimed`, a report
  that names who did it is `reported`.
- Civilians are never individuals. An `individual` actor requires `us_person_data: individuals`; an organization
  requires `organizations` or `individuals`.
- Every `source_ids` entry must be a `sources[].id` in the same item.

**Framing by side.** Tag each source with `owner` and `perspective`, and list the perspective labels in the feed
header. A program can then show how each side's media tells the same event, as Watchfloor does, and COP can split any
item's coverage by perspective.

Worked example: the fourth item in [`tests/fixtures/good.geojson`](../tests/fixtures/good.geojson), a fictional
reported strike with a party, the affected port and civilians, sourced to one outlet from each side. A ransomware
claim on a leak site would read:

```json
"actors": [
  { "name": "Group X", "role": "responsible", "actor_type": "criminal_group", "status_class": "claimed",
    "source_ids": ["leak-site"] },
  { "name": "Example Freight Company", "role": "affected", "actor_type": "company", "country": "US",
    "status_class": "claimed", "source_ids": ["leak-site"] }
]
```

with `us_person_data: "organizations"`, because the victim is a US organization.

## Conditional fields

| When | Required | Basis |
|---|---|---|
| `tier` anomaly | `baseline_ref` {id, window, type fixed/rolling/both, version; from 2.1 optional `flag_rate`}; see the revision 2.1 meaning above | JP 2-01.3 conditioning warning |
| a judgment (`tier` warning, or `kind` assessment or forecast) | `summary`; `probability` with matching `likelihood_term`; `confidence` and `confidence_basis`; `alternatives[]` each with `hypothesis` and `tell_apart`; `change_from_prior` (and `change_reason` if it changed); `requirement_ids` or `warning_problem_id` | ICD 203 standards 2, 4, 5, 6, 7 |
| `kind` forecast | `resolution` {rule, source, resolve_by} and `valid_until` | Verdict pre-registration |
| `indicator_id` set | `hypothesis_id`, `direction` (supports/refutes/neutral), `indicator_state` (present/absent/no_data) | CIA Tradecraft Primer |
| `msg_type` update, cancel or error | `supersedes` | CAP 1.2 references |

Keep the raw copy of any dynamic web source for at least a year (ICS 206-01 and ICD 206); `evidence_hash` and
`archive_url` point to it.

## Tags

| Tag | Values | Source |
|---|---|---|
| `ie_aspect[]` | informational, physical, human (old "cognitive" maps to human) | Joint Concept for Operating in the Information Environment (2018); SOIE glossary quoting JP 3-04 |
| `pmesii_pt[]`, `ascope[]`, `continuum` | operational variables; civil considerations; cooperation/competition/armed conflict | FM 3-0; JP 3-57; JCC |
| `ncf[]` and derived `sector[]` | CISA's 55 National Critical Functions; the 16 sectors follow from the kit's published crosswalk | CISA NCF Set (2019) |
| `lifeline[]` | `{id, status}` for FEMA's eight lifelines; status unknown/significant/moderate/minimal/baseline | FEMA Toolkit 2.1 |
| `response_stage` | `ladder:value`, e.g. `pager:orange`, `easa_czib:active`, `state_travel_advisory:level_4` | each ladder's owner |
| `disarm_technique[]` | DISARM technique ids (influence operations only) | DISARM |

All vocabularies live in [`vocab/`](../vocab). Change them there, rebuild (`python tools/build_js.py`,
`python tools/build_schema.py`), run the tests, then sync to each program.
