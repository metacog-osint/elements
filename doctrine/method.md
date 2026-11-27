# Elements method (doctrine summary)

Elements collects natural-hazard alerts every hour from the authorities that issue them: USGS earthquakes with their
PAGER impact alert, GDACS multi-hazard alerts, NOAA National Hurricane Center storms, and Copernicus EMS rapid-mapping
activations. It states them in the terms of The Intelligence Company's doctrine kit (`doctrine/kit/`).

## Anomaly versus warning
Everything Elements publishes is a measurement of what an authority said (kind observation), carrying that
authority's own alert ladder (`pager:*`, `gdacs:*`, `cems:*`). An alert above the bottom rung is an anomaly. PAGER and
GDACS alerts are model estimates published within minutes and revised; a revision replaces the earlier value and
counts in warning problem EL-WP-1 as a possible artefact.

## Places
Each event is drawn at the point its source gives; its country is the one that point falls in (offshore events have
none). Cyclones, droughts and floods reach well beyond their point.

## Fire and heat detections (NASA FIRMS)
VIIRS detections from NOAA-20, NOAA-21 and Suomi-NPP, nominal and high confidence, from the past 24 hours, gathered into
half-degree cells. With the free FIRMS key Elements uses the FIRMS area API, which adds real-time and ultra-real-time
detections; without it, or when the API fails for a satellite, it reads FIRMS's public files (near-real-time only,
about three hours behind). The health line says which was used and how many of the key's transactions a run spent,
and names a satellite that answered with no rows. Suomi-NPP's data delivery ended on 2 Nov 2026 (NOAA NESDIS); it is
still asked, and shows as "no rows".

These are detections, not fires. A fire is counted again on each overpass of each satellite, and FIRMS's
near-real-time data does not separate fires from gas flares, volcanoes and industrial heat sources. Each cell is
counted to the country at its centre of detections, so cells on a border all go to one side. The feed carries one
item per country with at least 10 detections; an item already open stays while its country has at least 5, so a
count near the floor does not end and reopen the item from one run to the next. The cells themselves are in
`fires.json`, not the feed.

`data/firms_daily.json` records each country's detections per complete UTC day from 30 Oct 2026. A country's count
is judged against two baselines, and it is an anomaly only when it is high against both:
- **Its past four weeks:** at least 3 times the median of its daily detections over the past 28 complete UTC days (a
  day on file without the country counts as 0), and at least 50 detections. The item stays routine until the file
  holds 14 days.
- **The same weeks of earlier years:** above the 95th percentile (by nearest rank, so no more than 5% of the readings
  are above it) of the country's daily detections from 15 days before to 15 days after the same date in each earlier
  year of FIRMS's archive. The archive is FIRMS's yearly country files for VIIRS on NOAA-20, standard processing, from
  1 Apr 2018 to the last complete year, counted per country and UTC day in `catalog/firms_climatology.json.gz` by
  `tools/firms_climatology.py`. Each half-degree cell's detections on a day go to the country at that day's centre of
  detections, with the same outlines as the live record. The archive holds one satellite and the live record two
  (NOAA-20 and NOAA-21), so the archive's counts are doubled. A year counts when more than half its window is on file,
  and the test applies once 3 earlier years count. Six days with no detection anywhere in the archive (19-22 Jul 2023,
  30 Sep 2023, 4 Feb 2024) are gaps in the data, not days without fire, and are left out.

A country with no seasonal record is judged on its past four weeks alone. The item carries the count as `signal`,
the 28-day median as `signal.expected`, the seasonal threshold in `measures.seasonal_threshold`, and both windows in
`baseline_ref` (`firms-country-seasonal`, type both; `firms-country-median`, rolling, for a country without a seasonal
record). A count over 3 times the median but not above the seasonal threshold stays routine, and
`measures.held_routine` says so: that is how the start of a dry season reads, when burning rises against the past four
weeks as it does every year. `baseline_ref.flag_rate` is the share of the seasonal window's readings above the
threshold, at most 5%. The seasonal record is rebuilt once a year: FIRMS publishes a year's country files months after
it ends (the 2025 files were last modified on 10 Oct 2026).

Back-test (`tools/firms_backtest.py`), 2022 to 2025, on the archive's own counts. It covers 29 countries: the 21 that
the 28-day rule alone flagged on more than 5% of their days in November 2026, and 8 controls. A country-day is judged
when it has at least 10 detections, the days that would have had a feed item (33,277 country-days):
- The 28-day rule alone (elements-feed-1.2) flagged 4,125 (12.4%), and 26 of the 29 countries on more than 5% of
  their own days. In the onset months of the West African and mainland Southeast Asian dry seasons it flagged 14% to
  44% of days (Ghana 43% in October to December; Cambodia 44% in November to January).
- Both rules together (elements-feed-1.3) flagged 1,046 (3.1%); the same onset months fell to 0% to 5.1%, except
  Burkina Faso (9.0%), where the season's start moves from year to year by more than the window absorbs.
- Six of the 29 countries were still flagged on more than 5% of their own days over the four years: Portugal 13.0%,
  Greece 7.7%, Nicaragua 5.9%, Chile 5.9%, the United Kingdom 5.5% and Papua New Guinea 5.1% (Gabon 4.96%). Sixteen
  were over 5% in at least one year. These are countries whose large fires come in episodes, and a year of large fires
  is above its own earlier years.
- Of 14 large fire episodes named in public reports, both rules together flagged 10 and the 28-day rule alone 12:
  for example the Evros fire in Greece (from 19 Aug 2023) on 10 days, with its peak, and Bolivia's 2024 season on 9.
  They missed the Valparaiso fires (Chile, Feb 2024; the archive's largest Chilean days, Feb 2023, set February's
  threshold), Honduras (Apr-May 2024) and Peru (Sep 2024), whose 28-day medians had already risen with the season, and
  Cambodia (Mar 2023), within its usual peak, which neither rule flags.
- Over all 187 countries with a judged day, the 28-day rule alone flagged 9.5% of country-days and 125 countries on
  more than 5% of their own days; both rules together flagged 2.8%, and 46 countries, among them most of the Balkans
  and the Caucasus, Ireland and Iceland.

On the live record, 13 to 26 Nov 2026, the 28-day rule alone flagged 67 country-days in 21 countries; both rules
together flag 11 in 7 (Colombia 16-19 Nov, Vietnam 16-17 Nov, Gabon, Honduras, South Africa, Greece and Papua New
Guinea). The earlier note on this page set a pooled rate (3.1% of all country-days) against the contract's 5% cap,
which applies to each subject: by the subject's own days the 28-day rule alone was well over it.

Limits. The archive is standard processing and the live record near-real-time; the difference between them is not
measured. The live ratio of two satellites to NOAA-20 alone was 1.98 worldwide over 21-26 Nov 2026, but 1.77 to 2.53
by country, so a country's threshold may sit a little high or low. The climatology is short (7 years and 9 months,
including the 2023-24 El Niño) and adjusts for nothing: a trend or a change in land use reads as a departure until the
years catch up. Method elements-feed-1.3 (1.2 had the 28-day rule alone).

## Volcanoes
USGS volcano alert levels and aviation colour codes for every US volcano above Normal or Green, with the previous
level and the responsible observatory's synopsis. Each is measured against Normal, and since 15 Nov 2026 (Tom: a
standing or lowered alert is not news) an item is an anomaly only when its alert was raised, it is newly elevated
(from Normal or unassigned), USGS gives no earlier level, or it stands at Warning or aviation code Red; a re-sent or
lowered alert below Warning is routine and still listed. The kit's `usgs_volcano` ladder (kit 0.3.1) gives the
response stage; with an older kit the items go out without one.

## States (`subdivisions`)
Since 15 Nov 2026 (kit 0.5.7) every US item with a place carries the ISO 3166-2 code of each state it is in
(`US-HI`), so a consumer can tell a hazard in Hawaii from one for all of the US: from NWS's own county codes for NWS
alerts, else from the item's point or shape on the kit's Natural Earth 1:10m state outlines (right to about 1 km at a
state line). Items for the whole country carry none.

The Smithsonian Global Volcanism Program's daily report would cover the rest of the world, but its site sits behind
bot protection that refuses scripted clients, and Elements does not work around that. Its weekly RSS feed answers
but was two weeks behind its web page on 31 Oct 2026. Until GVP grants access, GDACS's volcano alerts cover volcanoes
outside the US.

## US weather
National Weather Service alerts rated Severe or Extreme on CAP's four-step severity scale, merged by VTEC event so an
event issued in several segments is one item. Storm-based warnings keep the polygon NWS drew; county-based alerts
are placed at each named county's Census internal point (`catalog/us_counties.json`), and marine zones without
either link to the alert instead. Extreme is an anomaly against the CAP scale. The Storm Prediction Center's Day 1
categorical outlook gives one item per risk area from Marginal to High; Moderate and High are anomalies. Neither
scale is a kit ladder yet, so these items carry no response stage.

## European weather warnings (MeteoAlarm)
MeteoAlarm (EUMETNET) gathers the official warnings of 39 national weather services and publishes them as CAP, one
JSON file per country, under CC BY 4.0. Elements reads every file, keeps the actual, public warnings at MeteoAlarm's
yellow, orange and red awareness levels that have not expired (warnings starting later are included), and reads each
warning's English text. Green messages ("no particular awareness") and all-clear updates are dropped. MeteoAlarm's
files already leave out messages a later update replaced; a warning keeps one id across its updates, from the first
message in its chain of references.

Orange and red warnings are one item each; red (very dangerous) is an anomaly against MeteoAlarm's scale, as Extreme
is for NWS. Yellow warnings, hundreds on an ordinary day, are counted in one item per country with every warning in
force; the map shows each one (`meteoalarm.json`). MeteoAlarm's scale is not a kit ladder yet, so no response stage.

Places: a warning area the service drew as a polygon keeps it. Otherwise the area is placed at a point inside its
MeteoAlarm region (`catalog/meteoalarm_areas.json`, built from MeteoAlarm's geocodes file by
`tools/build_meteoalarm_areas.py`), found by region code, then by region name within the country (France gives NUTS3
codes only), and failing both at the country's label point; each item's precision says which. Each warning's own
credit line (Deutscher Wetterdienst's geometry: © GeoBasis-DE / BKG) is carried through.

A country whose file fails keeps its earlier warnings until they expire. The warnings themselves are not committed to
`data/` (about 300 KB a run, and they expire within hours); the health line counts them.

Elsewhere in the world no single feed allows reuse: WMO's Severe Weather Information Centre aggregates national CAP
warnings worldwide, but WMO's website terms allow only personal, non-commercial use, and each warning's copyright
stays with its issuing service. Other countries are added one by one once their own licence is checked.

## Tsunami messages
The two NOAA warning centres (NTWC in Alaska, PTWC in Hawaii) each publish their latest message as an Atom feed linking
a CAP file. Elements keeps every message for 30 days, one per centre and earthquake (a later message replaces an
earlier one), and publishes those from the last 7 days. Anything above an information statement is an anomaly. Items
are dated by when the message was sent; when a message gives an origin time more than 6 hours earlier, the item says
the centre's date may be wrong (PTWC's message for the 25 Oct 2026 Bonin Islands earthquake gave 24 Oct).

## US drought
The US Drought Monitor's weekly statistics give one national item: the cumulative share of the US in each category.
The map is fetched only when a new week appears and is snapped to a 0.05-degree grid for display. The Drought Monitor
states no licence; Elements credits its three producers. No baseline yet: week-on-week change is reported, not judged.
The item's `valid_until` is the next scheduled release (nine days after the map's date) plus two days, since the
Drought Monitor's own valid period (kept as `measures.valid_end`) ends three days before the next map is out. With no
newer map by then the item leaves the feed and the history log ends it.

## Earthquakes from two catalogues
EMSC's catalogue is matched to USGS's: the same earthquake if the origin times are within 90 seconds and the epicentres
within 150 km, closest in time first, each event used once. A match counts as independent corroboration, and adds EMSC
as a second source, only when EMSC's solution comes from another agency: EMSC sometimes carries USGS's own (authority
NEIC), and then the match is recorded but not counted. An EMSC earthquake with no USGS match becomes its own item; one
carrying NEIC's solution is left to USGS's feed. A missing match is not an error by either agency, since their
magnitudes differ and the 4.5 cut-off splits events between them.

An earthquake whose epicentre is in no country (most are at sea) keeps `countries` empty, so a join by country stays
strict. When USGS's place text names a reference town ("85 km S of Gorontalo, Indonesia"), the item carries
`measures.town_country`, the ISO code of the country named after the town (a US state counts as US; "Georgia",
which names both a state and a country, is read as the state west of the prime meridian and the country east of it). It is the town
USGS chose to describe the location, not a measured nearest coast; a region name ("Fiji region") gives none.

## US wildfires
NIFC's WFIGS service lists current incidents, including prescribed burns and fires contained months ago. Elements keeps
wildfires not declared out that are either short of full containment or were discovered in the last 14 days. Fires of
100 acres or more get a feed item; the map shows them all. FIRMS shows heat seen from space; NIFC names the fires and
says how far they are contained.

## Feed contract revision 2.1 (method elements-feed-1.1, 19 Nov 2026)
Every item also says what it is about, when, where and whether it changed, so readers such as COP can tell a standing
hazard from a new or a changed one:
- **Subject.** Each item's `subject_id` is its id: Elements' ids already name the thing read (an earthquake, a warning
  chain, a volcano, a country), never the run. An NWS alert without VTEC is one subject along its CAP chain, keyed on
  the chain's first message, as MeteoAlarm's warnings are.
- **Change.** `last_change` is stated where the source says it: a volcano's alert raised or lowered (at USGS's own
  change date), and the US Drought Monitor's map raised or lowered when the area in severe drought or worse (D2 to D4)
  moves by more than 1 percentage point week on week, otherwise standing (`none`). Everything else is filled from
  Elements' history log: new at its first sighting, raised, lowered or changed when its tier or alert rung moved, or
  standing for items already open on the log's first run (13 Nov 2026). No change is dated after publication.
- **Event times.** From the sources' own fields: an earthquake's or tsunami message's origin time, a warning's onset
  and end, an outlook's valid period, GDACS's event start (and end once it is no longer current; an event GDACS no longer marks current, or whose
  latest report is more than 7 days before Elements' last good read of GDACS, has ended and leaves the feed for the
  history log; while GDACS cannot be read, its last good copy is not aged out on the clock alone), a Copernicus EMS
  event date, a wildfire's discovery, the FIRMS window, the drought map's week (day precision). Volcano notices give
  none, and a country's count of warnings in force is no one event.
- **Place.** Every hazard is where it names (`place_basis: location`); `sea_areas` from the kit's sea gazetteer, empty
  on land and for country-level items.
- **Signal.** The rung each item's tier rests on: PAGER, GDACS, CAP severity, SPC category, tsunami message level,
  MeteoAlarm awareness level, volcano alert level (else aviation colour), FIRMS detections, D2-D4 drought area.
- **Corroboration.** An earthquake that EMSC locates from a solution not USGS's own is corroborated by two independent
  origins. `first_reported_at` is the origin time, since neither catalogue gives the time it first published;
  `corroborated_at` is the later of the two catalogues' last-update times, by when both had reported.
- **Grades.** Credibility 1 means confirmed by other sources (kit 0.6.2), so an item resting on one independence group
  grades its sources 2 at most (A1 becomes A2); an earthquake EMSC independently locates keeps USGS's A1.
- **Health.** Each source lane in the feed header carries a state: fresh (read on this run), failing (not read on this
  run, read within 48 hours), stale (no good read for 48 hours) or never.

## Not yet covered
Weather warnings outside the US and Europe, volcanoes outside the US beyond GDACS's alerts, and radiation: EPA RadNet offers only whole-year CSV files per city
(about 750 KB each, some 140 cities), and Elements will not pull that much every hour. A
missing source turns its layer grey ("no data"), never quiet.
