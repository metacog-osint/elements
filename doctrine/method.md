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

## Not yet covered
Volcanoes outside the US beyond GDACS's alerts, and radiation: EPA RadNet offers only whole-year CSV files per city
(about 750 KB each, some 140 cities), and Elements will not pull that much every hour. A
missing source turns its layer grey ("no data"), never quiet.
