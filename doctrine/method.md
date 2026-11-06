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
about three hours behind). The health line says which was used and how many of the key's transactions a run spent.

These are detections, not fires. A fire is counted again on each overpass of each satellite, and FIRMS's
near-real-time data does not separate fires from gas flares, volcanoes and industrial heat sources. Each cell is
counted to the country at its centre of detections, so cells on a border all go to one side. The feed carries one
item per country with at least 10 detections; the cells themselves are in `fires.json`, not the feed.

Fire items carry no anomaly tier yet: there is no baseline. `data/firms_daily.json` records each country's detections
per complete UTC day from 31 Oct 2026, so a baseline can be set once enough history exists. FIRMS's archive could
supply a seasonal one sooner.

## Volcanoes
USGS volcano alert levels and aviation colour codes for every US volcano above Normal or Green, with the previous
level and the responsible observatory's synopsis. Each is an anomaly against Normal. The kit's `usgs_volcano` ladder
(kit 0.3.1) gives the response stage; with an older kit the items go out without one.

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

## Earthquakes from two catalogues
EMSC's catalogue is matched to USGS's: the same earthquake if the origin times are within 90 seconds and the epicentres
within 150 km, closest in time first, each event used once. A match counts as independent corroboration, and adds EMSC
as a second source, only when EMSC's solution comes from another agency: EMSC sometimes carries USGS's own (authority
NEIC), and then the match is recorded but not counted. An EMSC earthquake with no USGS match becomes its own item; one
carrying NEIC's solution is left to USGS's feed. A missing match is not an error by either agency, since their
magnitudes differ and the 4.5 cut-off splits events between them.

## US wildfires
NIFC's WFIGS service lists current incidents, including prescribed burns and fires contained months ago. Elements keeps
wildfires not declared out that are either short of full containment or were discovered in the last 14 days. Fires of
100 acres or more get a feed item; the map shows them all. FIRMS shows heat seen from space; NIFC names the fires and
says how far they are contained.

## Not yet covered
Weather warnings outside the US and Europe, volcanoes outside the US beyond GDACS's alerts, and radiation: EPA RadNet offers only whole-year CSV files per city
(about 750 KB each, some 140 cities), and Elements will not pull that much every hour. A
missing source turns its layer grey ("no data"), never quiet.
