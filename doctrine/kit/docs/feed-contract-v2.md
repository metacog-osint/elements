# Feed contract v2 (`tic-feed/2`)

Every program publishes its items in this shape: GeoJSON first (a FeatureCollection whose features carry these fields
in `properties`, with `geometry: null` for items with no place), or JSON lines of flat items. The machine-readable form
is [`schema/feed-item-v2.schema.json`](../schema/feed-item-v2.schema.json); the tradecraft linter
(`python tic.py lint`) checks everything below, including the conditional rules. A worked example is
[`tests/fixtures/good.geojson`](../tests/fixtures/good.geojson).

## Feed header (FeatureCollection)

`contract`, `program`, `generated_at`, `licence`, `attribution`, and `language_key` (a link to the
[language key](language-key.md)). Optional: `perspectives`, a map from each `sources[].perspective` id to its label
(`{"russian_state": "Russian state and Kremlin-aligned media"}`), so readers and COP can name each side's media.

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
| `data_as_of`, `published_at` | when it was true; when we published it (UTC, ending in Z) | ICD 206 |
| `countries` | ISO 3166-1 alpha-2 codes, `[]` for none | |
| `coverage_fraction` | share of expected observations received | Primer quality-of-information check |
| `method_version` | the method that made the item | |
| `sources[]` | `id`, `publisher`, `author`, `title`, `outlet`, `source_type`, `url`, `published_at`, `accessed_at`, `licence`, `descriptor` (credibility, reliability, provenance, collector or tool), `grade` (Admiralty, e.g. B2), `lineage_id`, `independence_group`; optional `owner` (state, public, private, intergovernmental, ngo, individual, unknown) and `perspective` (the program's source group, e.g. `russian_state`) | ICS 206-01 (2 Dec 2024) citation fields, without classification fields; Admiralty system; owner and perspective from Watchfloor's source catalog |
| `geometry` or `visual` | a place on the map, or `{type, url}` for a graphic | ICD 203 standard 9; visual-first rule |

Optional on every item: `summary`, `evidence_hash` (`sha256:...`), `archive_url`, `requirement_ids[]`,
`precision_class`, `product_category`, `actors[]` (below), and the tags below.

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
| `tier` anomaly | `baseline_ref` {id, window, type fixed/rolling/both, version} | JP 2-01.3 conditioning warning |
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
