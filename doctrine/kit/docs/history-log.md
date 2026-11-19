# The history log (`tic-history/1`)

A program's feed carries what is active now. The history log keeps what was: every item the program has published,
kept after it leaves the feed. An item that is no longer active is not displayed, but it is never thrown away, because
comparing now with the past is a core use of the suite. Each program keeps its own log; COP gathers them into one
ledger for the suite. The format was first written for Elements (13 Nov 2026) and is the same for every program.

## What a run writes

Each run compares the feed just built with the items open after the last run and writes one line per change.

| Change | When |
|---|---|
| `new` | An item appears: the first time, or again after it ended |
| `changed` | Its `tier` or `response_stage` moved; or, with `--reading-key` (opt-in, 0.5.13), that property moved. Other edits only raise `updates` |
| `ended` | It left the feed while its source was read well on this run; or it was issued and ended between two runs and a catch-up query found it (then `new` and `ended` are written together, with `seen_live: false`) |

A failed fetch never ends anything. An item the linter held back (`dropped` in the feed) is not ended either.

**Subjects (kit 0.6.0).** An item with a `subject_id` (contract revision 2.1) is kept under its subject, not its id.
A program whose ids carry the day (`headwind:fx:TRY:2026-11-13`) then logs each day's reading as an update to one
open subject, and a tier move between days as a `changed` line, instead of a `new` and an `ended` every day. An item
without `subject_id` is kept under its id, as before. On the first run with subject ids, an open entry whose id is
the item's id moves to its subject, so a program with stable ids sees no lines at all. Two items of one subject in
the same feed are kept apart, the second under its own id (the linter notes it).

## A line

One JSON object per line, UTF-8, times in UTC.

| Member | Meaning |
|---|---|
| `format` | `tic-history/1` |
| `at` | The run that wrote the line |
| `change` | `new`, `changed` or `ended` |
| `id`, `program` | The item's id and its program |
| `subject_id` | The item's subject, when it has one (kit 0.6.0): the key the line is about |
| `lane` | The source lane: the item's first source's `lane` when it names one (0.6.0), otherwise its id; the key of that source in the program's health record |
| `first_seen`, `last_seen` | First and latest run that saw the item |
| `peak_tier` | The highest tier it reached |
| `updates` | How many times its content changed, apart from fields that change on every run |
| `was` | On `changed`: the tier and response stage before, and the reading key's value before when it moved |
| `ended_at`, `end_reason` | On `ended`. `ended_at` is the item's own `valid_until` when that falls between its last sighting and this run; otherwise this run's time, and the true end lies between `last_seen` and `ended_at` |
| `seen_live` | `false` when the item was never in a feed and came from a catch-up query |
| `item` | The full contract-v2 item as it stood (its last version, for `ended`) |

Because every line carries the full item, the log alone rebuilds the picture at any past time.

**A series under one id (0.5.13).** A program whose item stands for one series (a currency, a price index) and keeps the same id from one reading to the next passes `--reading-key data_as_of`: each new reading is then a `changed` line with the full item, and the reading before is no longer reported as ended. The value is stored apart from the status, so the first run with the option reports nothing for items already open. Programs whose ids carry the reading's date need nothing: each reading is `new`, and the one before `ended`. From
0.6.0 such a program can send `subject_id` instead (below), and `--reading-key` then works on the subject.

## Files

- `history/log/YYYY/MM/DD.jsonl`: today's lines. A day that has closed is gzipped once as `DD.jsonl.gz`, with no
  timestamp in the gzip header, and never rewritten.
- `history/state.json`: the items open after the last run, one per line, keyed by subject or id. From kit 0.6.0 it
  also holds `since` (the log's first run) and, per entry, `last_change` and `last_change_at` (when its state last
  moved, as the log saw it).
- `data/ended.geojson`, served beside the feed: the items that ended in the last 7 days and are not open again, newest
  end first. Not drawn on the map and not in the feed. Each feature is the item as it last stood, with a `history`
  member outside `properties`, so the item stays contract-valid.

## Adopting it in a program

1. Sync the kit (0.5.0 or later).
2. After the step that builds the feed, run:

   ```
   python doctrine/kit/tic.py history site/data/feed.geojson --dir history --ended site/data/ended.geojson
   ```

   Pass `--health <file>` when the program keeps a health record in its own file. Without it the command uses the
   feed's own `health` member. A lane counts as read when its `last_ok` equals its `checked_at` and, when the entry
   gives a `state`, that state is `fresh`, `late` or `up` (0.5.1). A program that withholds a source's items while
   the source still answers must mark that source stale in the record it passes, or the withheld items will be
   logged as ended.
3. Commit `history/` from the workflow with the data commit, in a way that does not start another run.
4. Add the address of `ended.geojson` to the program's entry in COP's `config/programs.json` (`"ended"`).

**Source ids finer than the health record.** An item whose lane the health record does not name can never end, and
the command warns about it. Name such source ids as a lane with `--lane-map`, once per rule; a `*` ends a prefix:
`--lane-map "usembassy-*=us-embassy-alerts"` (Cordon's embassy posts, 14 Nov 2026).

**A program with no health record.** Every lane then counts as read, which is right only when a failed source's last
items stay in the feed. If a failed fetch can empty part of the feed, give the command a health record first, or the
log will record ends that did not happen. As a guard, a run with no health record and no items at all ends nothing.

**Filling `last_change` (kit 0.6.0).** A program with no better knowledge of when its items changed adds
`--fill-last-change`. After logging, the command gives every feed item that does not state `last_change` the log's
own record, and rewrites the feed file with it (compact JSON):

| The log saw | `last_change`, `last_change_at` |
|---|---|
| The item's tier or response stage move since it opened | `raised`, `lowered` (the tier first, then the rung's severity on the same ladder) or `changed`, at that run |
| It open since a run after the log's first | `new`, at its first sighting |
| It there on the log's first run and never moving | `none`, no time (standing as long as the log has watched) |

The log's first run is `since` in the state; for a log begun before 0.6.0 the command reads it from the log's first
line. Items a program states itself are kept as they are. Run the fill before the feed is published, and lint after
it. From Python: `fill_last_change(feed, state)` after `update()`, or `run(..., fill=True)`.

**The run's time (kit 0.6.3).** `--now` sets it. Without `--now` it is the feed's own `generated_at` (the wall
clock when the feed has none, or when that is later than the clock), so nothing the run stamps is later than the items'
`published_at` and the lint after the fill passes. Before 0.6.3 the default was the wall clock, and a program running
`--fill-last-change` had to pass `--now` with the feed's `generated_at` itself.

**From Python.** `tic_doctrine.history.update(state, feed, health, now, caught)` is pure and returns the new state and
the lines; `run()` does the same against files. `caught` takes items from a program's own catch-up query (Elements
asks NWS for Severe and Extreme alerts issued since the last good read). `ok=` and `lane_of=` let a caller name the
lanes and say which were read, as COP does with a program per lane.

## Limits

- The log starts when a program adopts it. Earlier history can be rebuilt only where the program's data were
  committed to git, as Elements did for 31 Oct to 14 Nov 2026; rebuilt lines carry a `backfill` member.
- An item issued and ended between two runs is missed unless the program has a catch-up query for that source.
- `ended_at` is exact only when the item carries its own end time.
