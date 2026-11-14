# Elements history

Every item Elements has published, kept after it leaves the feed: Elements' own historical record, part of The
Intelligence Company's historical dataset. Written by `elements/history.py` (format `tic-history/1`).

- `log/YYYY/MM/DD.jsonl` (today) and `DD.jsonl.gz` (closed days, written once): one line per change, `new`,
  `changed` (tier or response stage moved) or `ended` (left the feed while its source was read successfully, or an
  NWS alert issued and ended between two runs). Each line carries the full contract-v2 item as it stood, with
  first_seen, last_seen, ended_at, end_reason, peak_tier and the number of updates. Times UTC.
- `state.json`: the items open after the last run.
- The site serves the last 7 days of ended items at `data/ended.geojson`, not drawn on the map and not in the feed.

From 2026-10-31 to 2026-11-14T02:06:34Z the log was rebuilt from this repository's git history of `data/` (419 runs) by
`tools/history_backfill.py`; those lines carry a `backfill` member. Limits of that part: FIRMS and MeteoAlarm data
were not in git, so their items start on the first live run; a run that changed no data made no commit; warnings
issued and ended between two runs are missing (the live catch-up started later); the items were rebuilt with the
code of the backfill, so their wording can differ from what was published at the time.
