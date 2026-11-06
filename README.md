# Elements

**Earthquakes, volcanoes, cyclones, weather warnings, floods, droughts, fires and disaster mapping, as the issuing authorities report them, on one map.**
Map: https://elements.theintelligence.company/ · Feed: https://elements.theintelligence.company/data/feed.geojson

Elements collects natural-hazard alerts every hour, straight from the authorities that issue them:

| Source | What it gives | Licence |
|---|---|---|
| USGS earthquake summary feed (M4.5+, past 7 days) | Origin, magnitude, depth and the PAGER impact alert | US public domain |
| USGS Volcano Hazards Program, elevated volcanoes | Alert level and aviation colour code for US volcanoes above Normal, with the change and the observatory's synopsis | US public domain |
| NOAA National Weather Service alerts (api.weather.gov) | Warnings and watches rated Severe or Extreme, by polygon or county | US public domain |
| NOAA Storm Prediction Center Day 1 convective outlook | Risk areas from Marginal to High | US public domain |
| NOAA tsunami warning centres (NTWC, PTWC): Atom feeds and CAP messages | Tsunami messages from the last 7 days, with the earthquake's preliminary magnitude | US public domain |
| MeteoAlarm (EUMETNET): warnings of 39 European national weather services, one CAP JSON file per country | Yellow, orange and red warnings in force, by the service's polygon or a point in each region named | CC BY 4.0; data provided by EUMETNET members |
| MeteoAlarm geocodes file (region outlines; one point per region kept) | Places warnings that name regions without a polygon | No licence stated (not verified); credited |
| US Drought Monitor (NDMC University of Nebraska-Lincoln, USDA, NOAA) | Weekly share of the US in each drought category, and the map | No licence stated (not verified); credited |
| EMSC event service (seismicportal.eu), M4.5+, past 7 days | A second, independent earthquake catalogue: corroborates USGS events and adds those USGS lists below 4.5 | CC BY 4.0 |
| NIFC WFIGS current incident locations | US wildfires still being fought or found in the last 14 days: size, containment, county | No licence stated (not verified); credited |
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
- MeteoAlarm warnings: orange and red are one feed item each (red is an anomaly, as NWS Extreme is); yellow, hundreds
  a day, are counted per country in the feed and drawn one by one on the map. Green messages and all-clears are
  dropped. A country whose file fails keeps its warnings until they expire; warnings are not committed to `data/`.
- Each event is drawn at the point its source gives, and its country is the one that point falls in (offshore events
  have none). Cyclones, floods and droughts reach well beyond their point.

Everything Elements publishes is a measurement of what an authority said, in The Intelligence Company's feed contract
v2 (`tic-feed/2`), and passes the doctrine kit's tradecraft linter before it is published. Method:
`doctrine/method.md`.

Not yet covered: weather warnings outside the US and Europe (WMO's worldwide Severe Weather Information Centre may
not be republished; other countries are added as their licences are checked), volcanoes outside the US beyond
GDACS's alerts (the Smithsonian's daily report refuses automated readers) and radiation monitoring (EPA RadNet offers
only whole-year files per city).

## Running it

```
python tools/elements.py collect   # fetch every source into data/ (a failing source keeps its last good data)
python tools/elements.py build     # write site/ (map page, feed.geojson, fires.json, meteoalarm.json, wildfires.json, health.json)
python tools/elements.py check     # the feed passes the doctrine kit's linter; registers are valid
python tests/test_elements.py
python tests/test_volcanoes.py
python tests/test_weather.py
python tests/test_tsunami_drought.py
python tests/test_meteoalarm.py
python tests/test_emsc_nifc.py
python tools/build_counties.py   # refresh catalog/us_counties.json from the Census Gazetteer (yearly)
python tools/build_meteoalarm_areas.py   # refresh catalog/meteoalarm_areas.json when MeteoAlarm publishes new geocodes
```

Standard-library Python only. `update.yml` runs hourly: collect, commit `data/` when its content changed, build and
publish to GitHub Pages.

Code under the MIT licence. Country outlines from Natural Earth (public domain); map drawn with Leaflet (BSD
2-Clause). A project of The Intelligence Company.
