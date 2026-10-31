# tic-doctrine

The shared doctrine kit for The Intelligence Company's programs (Noisefloor, Watchfloor, Context, Vigil, PropertyCast,
and the programs still to come). It turns each program's measurements into judgments that can be read the same way,
drawn on one map (COP) and scored (Verdict).

**What is in it**

| Path | What |
|---|---|
| `vocab/` | Reference vocabularies: ICD 203 likelihood with UK and Kent crosswalks; the confidence rubric; contract enums; JP 3-04 information aspects, PMESII-PT, ASCOPE, the competition continuum; CISA's 55 National Critical Functions with a published sector and lifeline crosswalk; FEMA's eight lifelines and status colours; response ladders (PAGER, GDACS, Copernicus EMS, IFRC, EASA, State Department); Admiralty grades; ICD 203's nine tradecraft standards; actor roles and types, and source owners, for characterising entities and sides without friend-or-foe labels |
| `schema/` | Feed contract v2 as JSON Schema |
| `python/tic_doctrine/` | Likelihood, confidence, contract checks, the tradecraft linter, register checks, source health, withholding counts (standard library only) |
| `js/tic-doctrine.js` | The same likelihood, confidence, lifeline and ladder logic for web pages (ES module, no dependencies) |
| `docs/` | The contract, the reader's language key, the confidence rubric, the sources-and-withholding page |
| `templates/doctrine/` | A program's registers: requirements, indicators and warning problems, assumptions, function map, sources, method |
| `tools/` | `sync.py` copies the kit into a program as `doctrine/kit/`; `build_js.py` and `build_schema.py` regenerate from `vocab/` |

**Use in a program**

```
python tools/sync.py D:/Projects/<program>            # vendor the kit into <program>/doctrine/kit/
python doctrine/kit/tic.py lint <feed>.geojson --doctrine doctrine
python doctrine/kit/tic.py registers doctrine
python doctrine/kit/tic.py health doctrine/sources.json --out doctrine/health.json
```

**Tests:** `python tests/test_kit.py` and `node tests/test_js.mjs`.

**Claims.** The methods are aligned with the principles of ICD 203, 206 and 208. Those directives bind US Intelligence
Community elements only; this is an independent, non-commercial research effort, so it never claims compliance. Only
released doctrine is cited.

Code: MIT. Vocabulary files restate public US government and allied publications, credited in each file.
