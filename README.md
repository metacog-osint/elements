# Elements

**Earthquakes, cyclones, floods, droughts, fires and disaster mapping, as the issuing authorities report them, on one map.**
Map: https://metacog-osint.github.io/elements/ · Feed: https://metacog-osint.github.io/elements/data/feed.geojson

Elements collects natural-hazard alerts every hour, straight from the authorities that issue them:

| Source | What it gives | Licence |
|---|---|---|
| USGS earthquake summary feed (M4.5+, past 7 days) | Origin, magnitude, depth and the PAGER impact alert | US public domain |
| GDACS event list (EC Joint Research Centre and UN OCHA), past 14 days | Alerts for cyclones, floods, droughts, volcanoes, earthquakes and wildfires | Reuse with attribution |
| NOAA National Hurricane Center (CurrentStorms.json) | Active Atlantic and eastern Pacific storms | US public domain |
| Copernicus EMS rapid-mapping activations | Disasters an authority asked the EU to map from satellite imagery | Free and open, © European Union |
| NASA FIRMS (VIIRS on NOAA-20, NOAA-21 and Suomi-NPP), past 24 hours | Fire and heat detections, in half-degree cells and per country | NASA open data, with acknowledgement of LANCE FIRMS |

## How it reads the sources

- PAGER and GDACS alerts are model estimates of impact, issued within minutes and revised. Elements keeps each
  authority's own ladder (`pager:yellow`, `gdacs:red`, `cems:activated`); anything above the bottom rung is an anomaly.
- GDACS returns at most 100 events per query, so Elements asks twice: every orange and red alert, then green cyclones,
  floods, volcanoes and droughts. Green earthquakes are left to USGS, and green wildfires (hundreds a fortnight) are
  not collected. An empty answer means nothing matched, not a failure.
- A GDACS alert is the highest the event has reached; the latest episode's alert is kept beside it. For cyclones,
  GDACS pairs the storm's latest stage with the event's maximum wind, so Elements gives the wind alone.
- Copernicus activations are shown when open or less than 60 days old.
- FIRMS gives detections, not fires: a fire is counted on every overpass, and gas flares, volcanoes and industrial
  heat are detected too. With the free key (`FIRMS_MAP_KEY`, an Actions secret) Elements uses the FIRMS API, which
  adds real-time detections; without it, FIRMS's public files, about three hours behind. Each country's daily count
  is kept in `data/firms_daily.json` to build a baseline; the hourly cells are not committed.
- Each event is drawn at the point its source gives, and its country is the one that point falls in (offshore events
  have none). Cyclones, floods and droughts reach well beyond their point.

Everything Elements publishes is a measurement of what an authority said, in The Intelligence Company's feed contract
v2 (`tic-feed/2`), and passes the doctrine kit's tradecraft linter before it is published. Method:
`doctrine/method.md`.

Not yet covered: volcano alert levels (USGS and the Smithsonian), US weather warnings, and radiation monitoring.

## Running it

```
python tools/elements.py collect   # fetch every source into data/ (a failing source keeps its last good data)
python tools/elements.py build     # write site/ (map page, feed.geojson, fires.json, health.json)
python tools/elements.py check     # the feed passes the doctrine kit's linter; registers are valid
python tests/test_elements.py
```

Standard-library Python only. `update.yml` runs hourly: collect, commit `data/` when its content changed, build and
publish to GitHub Pages.

Code under the MIT licence. Country outlines from Natural Earth (public domain); map drawn with Leaflet (BSD
2-Clause). A project of The Intelligence Company.
