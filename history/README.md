# Elements history

Every item Elements has published, kept after it leaves the feed: Elements' own historical record, part of The
Intelligence Company's historical dataset. Written by `elements/history.py` (format `tic-history/1`).

- `log/YYYY/MM/DD.jsonl` (today) and `DD.jsonl.gz` (closed days, written once): one line per change, `new`,
  `changed` (tier or response stage moved) or `ended` (left the feed while its source was read successfully, or an
  NWS alert issued and ended between two runs). Each line carries the full contract-v2 item as it stood, with
  first_seen, last_seen, ended_at, end_reason, peak_tier and the number of updates. Times UTC.
- `state.json`: the items open after the last run.
- `meteoalarm/YYYY-MM-DD.jsonl` (today) and `.jsonl.gz` (closed days, written once): every yellow MeteoAlarm warning,
  one line when first seen and another each time it changes (`change` is `new` or `changed`), with the national
  service (`sender`), type, areas, window and the CAP identifier. Orange and red warnings are in `log/`.
  `meteoalarm/state.json` holds the yellow warnings still in force, to avoid logging them again. Source: MeteoAlarm
  (EUMETNET), CC BY 4.0 as stated on feeds.meteoalarm.org: data provided by EUMETNET members; each line carries the
  service's own licence string in `credit`. Starts with the first run of this archive; earlier yellow warnings were not kept.
- `nws_minor/YYYY-MM-DD.jsonl` (`.gz` when closed): every NWS alert message rated Moderate or Minor, one line per
  message, read by issue time so alerts issued and ended between runs are kept. Long description and instruction text
  are left out; `url` is the message at api.weather.gov. US public domain. Starts 24 Nov 2026, reading back 72 hours.
- `gdacs_green_wildfires/YYYY-MM-DD.jsonl` (`.gz` when closed): GDACS green wildfire events, one line when first seen
  and one each time the event changes. Source: GDACS (EC Joint Research Centre and UN OCHA).
- Low-confidence FIRMS cells are in the monthly `firms-cells-YYYY-MM` release as `firms-low-cells-*.json.gz`, not here.
- These three lanes are kept for the record. They are outside the feed, the map and its tiers.
- The site serves the last 7 days of ended items at `data/ended.geojson`, not drawn on the map and not in the feed.

From 2026-10-31 to 2026-11-14T03:36:30Z the log was rebuilt from this repository's git history of `data/` (422 runs) by
`tools/history_backfill.py`; those lines carry a `backfill` member. Limits of that part: FIRMS and MeteoAlarm data
were not in git, so their items start on the first live run; a run that changed no data made no commit; warnings
issued and ended between two runs are missing (the live catch-up started later); the items were rebuilt with the
code of the backfill, so their wording can differ from what was published at the time.
