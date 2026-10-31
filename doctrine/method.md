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

## Not yet covered
Fires from NASA FIRMS (needs a free key), volcano alert levels from USGS and the Smithsonian, US weather warnings, and
the US nuclear and radiation lane. A missing source turns its layer grey ("no data"), never quiet.
