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

## Not yet covered
Volcano alert levels from USGS and the Smithsonian, US weather warnings, and the US nuclear and radiation lane. A
missing source turns its layer grey ("no data"), never quiet.
