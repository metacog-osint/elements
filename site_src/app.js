/* Elements map page. Reads data/feed.geojson (the program's tic-feed/2 feed, built by tools/elements.py),
 * data/fires.json (FIRMS detections in half-degree cells), data/health.json and geo/world.json (Natural Earth
 * outlines). Text is inserted as text, never HTML. Times go
 * through the shared TicTime module. */
(function () {
  "use strict";
  var T = window.TicTime;
  var RANK = { green: 0, yellow: 1, orange: 2, red: 3 };
  var HAZ = { "tropical cyclone": ["TC", "Tropical cyclone"], flood: ["FL", "Flood"], drought: ["DR", "Drought"],
    volcano: ["VO", "Volcano"], earthquake: ["EQ", "Earthquake"], wildfire: ["WF", "Wildfire"] };
  var NHC = { TD: "Tropical depression", TS: "Tropical storm", HU: "Hurricane", STD: "Subtropical depression",
    STS: "Subtropical storm", PTC: "Potential tropical cyclone", PT: "Post-tropical cyclone" };

  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function h(tag, attrs, kids) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) { if (attrs[k] != null) e.setAttribute(k, attrs[k]); }
    (kids || []).forEach(function (c) { if (c != null) e.append(c instanceof Node ? c : document.createTextNode(String(c))); });
    return e;
  }
  function when(iso) { return iso ? T.format(iso) : "—"; }
  // Leaflet inserts a string tooltip as HTML; a text node keeps source text as text.
  function tip(text) { return h("div", { "class": "tip" }, [text]); }
  function link(url, text) { return url ? h("a", { href: url, rel: "noopener" }, [text]) : text; }
  // A row may carry r.cls ("outside": a place outside the viewer's area, dimmed).
  // A long table shows its first rows (10 on a phone, 15 wider; each table puts the strongest or newest rows first)
  // and "Show all N", with a find box at 25 rows or more: the hub's tic-fold.js, at every width, as on Cordon.
  function table(head, rows, numCols) {
    numCols = numCols || {};
    return h("table", { "data-tic-fold": "", "data-tic-fold-find": "" }, [h("thead", null, [h("tr", null, head.map(function (x, i) { return h("th", { "class": numCols[i] ? "num" : null }, [x]); }))]),
      h("tbody", null, rows.map(function (r) {
        return h("tr", { "class": r.cls || null }, r.map(function (c, i) {
        return h("td", { "class": numCols[i] ? "num" : null }, [c]); })); }))]);
  }
  function empty(text) { return h("p", { "class": "empty" }, [text]); }
  function alertColor(a) { return a && RANK[a] != null ? css("--a-" + a) : css("--unrated"); }
  function badge(a, label) { return h("span", { "class": "badge a-" + (a || "none") }, [label || a || "none"]); }
  function lane(f) { return f.properties.id.split(":")[1]; }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  // Wheel zoom stays off until the reader clicks the map, so scrolling the page never gets trapped in it.
  // The opening view fits the whole world's width, so the Pacific (Alaska, Hawaii, the Aleutian and Tonga trenches) is in view.
  // Fitted by width only: the map is wide and short, so fitting latitudes too would shrink the world.
  var openZoom = Math.max(1, Math.floor(Math.log2((document.getElementById("map").clientWidth || 768) / 256) * 4) / 4);
  var map = L.map("map", { worldCopyJump: true, minZoom: 1, maxZoom: 8, zoomSnap: 0.25, scrollWheelZoom: false })
    .setView([25, 0], openZoom);
  map.once("click", function () { map.scrollWheelZoom.enable(); });
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution("Natural Earth · USGS · EMSC · GDACS · NOAA · NIFC · MeteoAlarm · Copernicus EMS · NASA FIRMS");
  // (USGS covers both the earthquake and the volcano layers.)
  var layers = {};
  var gdMarkers = {};  // GDACS map markers by item id, for "Show on map" in the alert list

  function quakeRadius(m) { return Math.max(3, 3 + (m - 4.5) * 2.6); }
  var FIRE_BREAKS = [[100, "100+"], [20, "20–99"], [5, "5–19"], [1, "1–4"]];
  function fireStep(n) { return n >= 100 ? 4 : n >= 20 ? 3 : n >= 5 ? 2 : 1; }
  function num(n) { return Number(n).toLocaleString("en-US"); }

  // US Drought Monitor's own category colours (D0 to D4), from its metadata page.
  var DM_COLORS = ["#ffff00", "#fcd37f", "#ffaa00", "#e60000", "#730000"];
  var DM_NAMES = ["Abnormally dry", "Moderate drought", "Severe drought", "Extreme drought", "Exceptional drought"];
  var TSU = { information: "information statement", threat: "threat message", watch: "watch", advisory: "advisory", warning: "warning" };

  // "My area" (tic-area.js; 16 Nov 2026, after Cordon): hazards outside the viewer's area are dimmed on the map
  // and in the tables, never hidden. An item is judged by the state its feed item names (`subdivisions`), else by its
  // point or shape. Country tables (Europe by country, fires by country, GDACS by hazard, US drought) are not dimmed.
  var A = window.TicArea;
  function inArea(item) { return !A || A.contains(item); }
  // An NWS warning for marine zones names only marine codes (no land county) and has no shape, so the feed gives it no
  // `subdivisions`: on this page it is placed in the state of the office that issued it ("NWS Fairbanks AK"), so
  // Alaska's Arctic warnings stay lit when Alaska is chosen. Every NWS item with a land county or a shape has its own.
  function subsOf(p) {
    if (p.subdivisions && p.subdivisions.length) return p.subdivisions;
    if (lane({ properties: p }) !== "nws") return undefined;
    var st = / ([A-Z]{2})$/.exec((p.measures || {}).office || "");
    return st ? ["US-" + st[1]] : undefined;
  }
  function tag(lyr, f) {
    lyr._item = { subdivisions: f.properties.subdivisions, countries: f.properties.countries, geometry: f.geometry };
    return lyr;
  }
  function leaves(group, fn) {
    group.eachLayer(function (l) { if (l.eachLayer && !l._item) leaves(l, fn); else fn(l); });
  }
  function itemOf(l) {
    if (l._item) return l._item;
    if (l.feature) return { subdivisions: (l.feature.properties || {}).subdivisions, countries: (l.feature.properties || {}).countries,
      geometry: l.feature.geometry };
    if (l.getLatLng) { var ll = l.getLatLng(); return { geometry: { type: "Point", coordinates: [ll.lng, ll.lat] } }; }
    return null;
  }
  function dim(feats) {
    var all = !A || A.get().kind === "all";
    Object.keys(layers).forEach(function (k) {
      if (k === "drought") return;  // national weekly categories, not a place-bound notice
      leaves(layers[k], function (l) {
        var ok = all || inArea(itemOf(l));
        if (l.setStyle) {
          if (!l._base) l._base = { opacity: l.options.opacity == null ? 1 : l.options.opacity, fillOpacity: l.options.fillOpacity };
          l.setStyle(ok ? l._base : { opacity: 0.15, fillOpacity: 0.04 });
        } else if (l.setOpacity) {
          l.setOpacity(ok ? 1 : 0.22);
        }
      });
    });
    var note = document.getElementById("area-note");
    if (all) {
      note.textContent = "Area: everywhere. Choose one with the Area button at the top to dim hazards elsewhere.";
      return;
    }
    var n = { alert: 0, quake: 0, weather: 0, volcano: 0, fire: 0, cells: 0, other: 0 };
    feats.forEach(function (f) {
      var p = f.properties, ln = lane(f);
      if (ln === "firms" || ln === "usdm" || /:in-force$/.test(p.id)
        || !inArea({ subdivisions: subsOf(p), countries: p.countries, geometry: f.geometry })) return;
      if (p.tier === "anomaly") n.alert += 1;
      if (ln === "usgs" || ln === "emsc") n.quake += 1;
      else if (ln === "nws" || ln === "spc" || ln === "meteoalarm") n.weather += 1;
      else if (ln === "usgs-volcano") n.volcano += 1;
      else if (ln === "nifc") n.fire += 1;
      else n.other += 1;
    });
    if (layers.firms) leaves(layers.firms, function (l) { if (inArea(itemOf(l))) n.cells += 1; });
    function part(c, one, many) { return c + " " + (c === 1 ? one : many); }
    note.textContent = "Your area: " + A.label() + ". In it: " + part(n.alert, "alert above the bottom rung", "alerts above the bottom rung") +
      ", " + part(n.quake, "earthquake", "earthquakes") + ", " + part(n.weather, "weather warning or outlook", "weather warnings or outlooks") +
      ", " + part(n.volcano, "volcano above Normal", "volcanoes above Normal") + ", " + part(n.fire, "wildfire", "wildfires") +
      ", " + part(n.other, "other hazard", "other hazards") + " and " + part(n.cells, "fire-detection cell", "fire-detection cells") +
      ". The rest are dimmed.";
  }

  function areaList(a) { return a.length > 3 ? a.slice(0, 3).join("; ") + " and " + (a.length - 3) + " more" : a.join("; "); }

  function draw(world, feats, fires, drought, euwx, nifcAll) {
    // Land goes in its own pane below the overlays: Leaflet stacks any SVG above any canvas in a pane, and the fire
    // canvas has to sit above the land.
    map.createPane("land").style.zIndex = 350;
    L.geoJSON(world, { pane: "land", interactive: false,
      style: { color: css("--border"), weight: 0.6, fillColor: css("--land"), fillOpacity: 1 } }).addTo(map);
    var by = { usgs: [], gdacs: [], nhc: [], cems: [], "usgs-volcano": [], nws: [], spc: [], tsunami: [], emsc: [], nifc: [] };
    feats.forEach(function (f) { (by[lane(f)] || []).push(f); });

    // Drought areas sit in their own pane just above the land, under everything else. Off until switched on: they
    // cover a third of the US.
    map.createPane("drought").style.zIndex = 360;
    layers.drought = L.layerGroup();
    ((drought && drought.polygons) || []).forEach(function (p) {
      L.geoJSON({ type: "Feature", geometry: { type: "MultiPolygon", coordinates: p.coordinates }, properties: {} },
        { pane: "drought", interactive: false, style: { stroke: false, fillColor: DM_COLORS[p.dm], fillOpacity: 0.55 } })
        .addTo(layers.drought);
    });

    // Fire cells, thousands of them, as dots on a canvas under every other layer. A half-degree cell is about a pixel
    // wide at world zoom, so each dot has a minimum size and grows with zoom to fill its cell.
    layers.firms = L.layerGroup();
    var fireCanvas = L.canvas({ padding: 0.5 });
    var fireColors = [null, css("--f1"), css("--f2"), css("--f3"), css("--f4")];
    var MIN_R = [0, 1.6, 2.1, 2.7, 3.3];
    var names = (fires && fires.names) || {}, cellDeg = (fires && fires.cell_deg) || 0.5, dots = [];
    function fireRadius(step) { return Math.max(MIN_R[step], 0.47 * cellDeg * 256 * Math.pow(2, map.getZoom()) / 360); }
    ((fires && fires.cells) || []).slice().sort(function (a, b) { return a[2] - b[2]; }).forEach(function (c) {
      var step = fireStep(c[2]);
      var dot = L.circleMarker([c[1], c[0]], { renderer: fireCanvas, stroke: false, radius: fireRadius(step),
        fillColor: fireColors[step], fillOpacity: 0.9 });
      dot.fireStep = step;
      dot._item = { countries: c[7] ? [c[7]] : undefined, geometry: { type: "Point", coordinates: [c[0], c[1]] } };
      dots.push(dot);
      // A function, so the text is built on hover: building ~6,000 tooltips up front (each formatting a time) held
      // the first draw for seconds.
      dot
        .bindTooltip(function () {
          return tip(num(c[2]) + " fire and heat detections" + (c[3] ? " (" + num(c[3]) + " high confidence)" : "")
            + "\nRadiative power " + num(c[4]) + " MW in all, largest " + num(c[5]) + " MW"
            + "\n" + (c[7] ? names[c[7]] || c[7] : "At sea or unassigned") + "\nLatest " + when(c[6]));
        }, { sticky: true })
        .addTo(layers.firms);
    });
    layers.firms.addTo(map);
    map.on("zoomend", function () { dots.forEach(function (d) { d.setRadius(fireRadius(d.fireStep)); }); });

    // Smaller quakes first so the large ones sit on top.
    layers.usgs = L.layerGroup();
    by.usgs.slice().sort(function (a, b) { return a.properties.measures.magnitude - b.properties.measures.magnitude; })
      .forEach(function (f) {
        if (!f.geometry) return;
        var m = f.properties.measures, c = f.geometry.coordinates;
        tag(L.circleMarker([c[1], c[0]], { radius: quakeRadius(m.magnitude), weight: 1, color: css("--mark-edge"),
          fillColor: alertColor(m.pager), fillOpacity: m.pager ? 0.9 : 0.55 }), f)
          .bindTooltip(tip(f.properties.title + "\n" + when(f.properties.data_as_of) + (m.depth_km != null ? ", depth " + m.depth_km + " km" : "")
            + (m.pager ? "\nPAGER " + m.pager : "\nNo PAGER alert issued")
            + (m.emsc ? (m.emsc.independent ? "\nAlso in EMSC's catalogue: M" + m.emsc.magnitude.toFixed(1) + " (" + m.emsc.authority + ")"
              : "\nEMSC carries USGS's own solution (not independent)") : "\nNot matched in EMSC's catalogue")
            + (m.tsunami_flag ? "\nUSGS tsunami flag set (a large ocean event; it does not mean a tsunami occurred)" : "")))
          .addTo(layers.usgs);
      });
    // EMSC earthquakes with no USGS match: hollow, dashed circles in the same layer.
    by.emsc.forEach(function (f) {
      if (!f.geometry) return;
      var m = f.properties.measures, c = f.geometry.coordinates;
      tag(L.circleMarker([c[1], c[0]], { radius: quakeRadius(m.magnitude), weight: 1.4, color: css("--unrated"), dashArray: "3 2",
        fill: true, fillOpacity: 0 }), f)
        .bindTooltip(tip(f.properties.title + "\n" + when(f.properties.data_as_of) + (m.depth_km != null ? ", depth " + m.depth_km + " km" : "")
          + "\nSolution: " + (m.authority || "EMSC") + ". Not in USGS's M4.5+ list (the two catalogues' magnitudes differ)."))
        .addTo(layers.usgs);
    });
    layers.usgs.addTo(map);

    // US wildfires being fought (NIFC), sized by acres.
    layers.nifc = L.layerGroup();
    (nifcAll || []).forEach(function (w) {
      var r = Math.max(2.5, Math.min(14, 1.6 * Math.log10(Math.max(w.acres, 1)) + 1));
      var dotw = L.circleMarker([w.lat, w.lon], { radius: r, weight: 1.2, color: css("--wildfire"), fillColor: css("--wildfire"), fillOpacity: 0.35 });
      dotw._item = { subdivisions: /^[A-Z]{2}$/.test(w.state || "") ? ["US-" + w.state] : undefined,
        countries: ["US"], geometry: { type: "Point", coordinates: [w.lon, w.lat] } };
      dotw
        .bindTooltip(tip(w.name + " (NIFC)\n" + Number(w.acres).toLocaleString("en-US") + " acres"
          + (w.contained != null ? ", " + w.contained + "% contained" : ", containment not reported")
          + "\n" + [w.county ? w.county + " County" : null, w.state].filter(Boolean).join(", ")
          + (w.discovered ? "\nDiscovered " + when(w.discovered) : "")))
        .addTo(layers.nifc);
    });
    layers.nifc.addTo(map);

    layers.gdacs = L.layerGroup();
    function gdAlert(f) { return (f.properties.response_stage || ":").split(":")[1]; }
    // Higher alerts drawn last, so they sit on top; green icons are smaller so they don't crowd out the rest.
    by.gdacs.slice().sort(function (a, b) { return (RANK[gdAlert(a)] || 0) - (RANK[gdAlert(b)] || 0); })
      .forEach(function (f) {
        if (!f.geometry) return;
        var p = f.properties, m = p.measures, c = f.geometry.coordinates;
        var a = (p.response_stage || "").split(":")[1];
        var code = (HAZ[m.hazard] || ["?"])[0];
        // Not a tab stop: the alert list beside the map is the keyboard and touch route to every marker (WCAG 2.5.8's
        // equivalent control, since these icons are under 24 px).
        gdMarkers[p.id] = tag(L.marker([c[1], c[0]], { keyboard: false, title: p.title,
          zIndexOffset: 100 * (RANK[a] || 0),
          icon: L.divIcon({ className: "gd-icon a-" + (a || "none"), html: "", iconSize: RANK[a] >= 2 ? [26, 19] : [19, 14] }) }), f)
          .bindTooltip(tip(p.title + "\n" + when(m.from) + " to " + when(m.to)
            + (m.latest_alert && m.latest_alert !== a ? "\nLatest episode: " + m.latest_alert : "")), { direction: "top" })
          .on("add", function (ev) { ev.target.getElement().textContent = code; })
          .addTo(layers.gdacs);
      });
    layers.gdacs.addTo(map);

    layers.nhc = L.layerGroup();
    by.nhc.forEach(function (f) {
      if (!f.geometry) return;
      var m = f.properties.measures, c = f.geometry.coordinates;
      tag(L.marker([c[1], c[0]], { keyboard: true, title: f.properties.title,
        icon: L.divIcon({ className: "nhc-icon", html: "", iconSize: [26, 26] }) }), f)
        .bindTooltip(tip(f.properties.title + "\nMoving " + (m.movement || "—") + "\nAdvisory " + when(f.properties.data_as_of)))
        .on("add", function (ev) { ev.target.getElement().textContent = m.classification || "TC"; })
        .addTo(layers.nhc);
    });
    layers.nhc.addTo(map);

    // US weather: SPC risk areas in SPC's own colours, then NWS warnings (an outline where the warning has its own
    // polygon, a dot at each county otherwise), orange for Severe and red for Extreme.
    layers.weather = L.layerGroup();
    by.spc.forEach(function (f) {
      if (!f.geometry) return;
      var m = f.properties.measures, col = m.fill || css("--a-orange");
      L.geoJSON(f, { style: { color: col, weight: 1.2, fillColor: col, fillOpacity: 0.28 } })
        .bindTooltip(tip(f.properties.title + "\nValid until " + when(m.expires)), { sticky: true }).addTo(layers.weather);
    });
    by.nws.forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties, m = p.measures, col = m.severity === "Extreme" ? css("--a-red") : css("--a-orange");
      var text = p.title + "\nUntil " + when(m.ends) + (m.areas.length > 1 ? "\n" + m.areas.length + " areas" : "");
      L.geoJSON(f, {
        style: { color: col, weight: 1.6, fillColor: col, fillOpacity: 0.15 },
        pointToLayer: function (pt, ll) { return L.circleMarker(ll, { radius: 3.5, weight: 1.2, color: col, fillColor: col, fillOpacity: 0.45 }); }
      }).bindTooltip(tip(text), { sticky: true }).addTo(layers.weather);
    });
    layers.weather.addTo(map);

    // European warnings (MeteoAlarm), every level from yellow to red, yellow first so the worse sit on top: the
    // polygon a service drew, or a dot at each region a warning names.
    layers.euwx = L.layerGroup();
    ((euwx && euwx.warnings) || []).forEach(function (w) {
      var col = css("--a-" + w.colour), lvl = w.level || 2;
      var text = cap(w.colour) + " " + w.type + " warning (" + ((euwx.names || {})[w.country] || w.country) + ")\n"
        + areaList(w.areas || []) + "\n" + (w.sender || "") + "\nFrom " + when(w.onset) + " until " + when(w.expires)
        + (w.credit ? "\n" + w.credit : "");
      var shape = w.polygons && w.polygons.length ? { type: "MultiPolygon", coordinates: w.polygons }
        : { type: "MultiPoint", coordinates: w.points || [] };
      L.geoJSON({ type: "Feature", geometry: shape, properties: {} }, {
        style: { color: col, weight: 1.4, fillColor: col, fillOpacity: 0.18 },
        pointToLayer: function (pt, ll) {
          return L.circleMarker(ll, { radius: 2 + lvl, weight: 1, color: css("--mark-edge"), fillColor: col, fillOpacity: 0.85 }); }
      }).bindTooltip(tip(text), { sticky: true }).addTo(layers.euwx);
    });
    layers.euwx.addTo(map);

    layers.tsunami = L.layerGroup();
    by.tsunami.forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties, m = p.measures, c = f.geometry.coordinates;
      var cls = m.level === "warning" ? "a-red" : m.level === "information" ? "a-none" : "a-orange";
      // Not a tab stop, like the GDACS icons: messages for one earthquake from both centres share a point and
      // neighbouring ones overlap, so the tsunami table below is the keyboard and touch route to each message
      // (WCAG 2.5.8's equivalent control). The icon's 24 px box still gives pointers a full-size target.
      tag(L.marker([c[1], c[0]], { keyboard: false, title: p.title, zIndexOffset: 500,
        icon: L.divIcon({ className: "ts-icon " + cls, html: "", iconSize: [30, 24] }) }), f)
        .bindTooltip(tip(p.title + "\n" + m.centre + ", " + when(p.data_as_of) + (m.headline ? "\n" + m.headline : "")
          + (m.origin_note ? "\n" + m.origin_note : "")))
        .on("add", function (ev) { ev.target.getElement().textContent = "TSU"; })
        .addTo(layers.tsunami);
    });
    layers.tsunami.addTo(map);

    layers.volcano = L.layerGroup();
    by["usgs-volcano"].forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties, m = p.measures, c = f.geometry.coordinates;
      var col = (m.aviation_color || "").toLowerCase();
      // Not a tab stop either: volcanoes in one arc sit closer than 24 px at the map's zoom, so the US volcanoes table
      // is the keyboard and touch route to each one (WCAG 2.5.8's equivalent control).
      tag(L.marker([c[1], c[0]], { keyboard: false, title: p.title, zIndexOffset: 400,
        icon: L.divIcon({ className: "vo-icon a-" + (col || "none"), html: "", iconSize: [24, 24] }) }), f)
        .bindTooltip(tip(p.title + "\n" + (m.synopsis || "") + "\n" + (m.observatory || "USGS") + ", " + when(p.data_as_of)
          + (m.nvews_threat ? "\nUSGS threat ranking: " + m.nvews_threat : "")))
        .addTo(layers.volcano);
    });
    layers.volcano.addTo(map);

    layers.cems = L.layerGroup();
    by.cems.forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties, m = p.measures, c = f.geometry.coordinates;
      tag(L.circleMarker([c[1], c[0]], { radius: 7, weight: 2.2, color: css("--cems"), fill: true, fillOpacity: 0, dashArray: m.closed ? "3 3" : null }), f)
        .bindTooltip(tip(p.title + "\n" + (m.category || "") + ", activated " + when(m.activated) + (m.closed ? " (closed)" : " (open)")))
        .addTo(layers.cems);
    });
    layers.cems.addTo(map);

    document.querySelectorAll(".layers input").forEach(function (box) {
      var l0 = layers[box.getAttribute("data-layer")];
      if (l0 && !box.checked && map.hasLayer(l0)) map.removeLayer(l0);
      box.addEventListener("change", function () {
        var l = layers[box.getAttribute("data-layer")];
        if (box.checked) l.addTo(map); else map.removeLayer(l);
      });
    });

    function sw(cls, style, label) { return h("span", null, [h("span", { "class": cls, style: style }), label]); }
    var fireKey = [h("span", { "class": "lg-h" }, ["Fire and heat detections per cell:"])].concat(FIRE_BREAKS.slice().reverse().map(function (b) {
      return sw("dt", "background:" + fireColors[fireStep(b[0])] + ";box-shadow:none", b[1]); }));
    document.getElementById("legend").replaceChildren.apply(document.getElementById("legend"), fireKey.concat([
      h("span", { "class": "lg-h" }, ["Alert:"]),
      sw("dt", "background:" + css("--a-green"), "green"), sw("dt", "background:" + css("--a-yellow"), "yellow"),
      sw("dt", "background:" + css("--a-orange"), "orange"), sw("dt", "background:" + css("--a-red"), "red"),
      sw("dt", "background:" + css("--unrated") + ";opacity:.6", "no PAGER alert"),
      h("span", null, ["Circle size: magnitude"]),
      h("span", null, [h("span", { "class": "gd-icon a-orange lg-icon" }, ["FL"]), "GDACS hazard: " + Object.keys(HAZ).map(function (k) {
        return HAZ[k][0] + " " + HAZ[k][1].toLowerCase(); }).join(", ")]),
      h("span", null, [h("span", { "class": "vo-icon a-orange lg-vo" }), "US volcano (aviation code)"]),
      h("span", null, [h("span", { "class": "wx" }), "US weather warning"]),
      h("span", null, [h("span", { "class": "eu" }), "European weather warning (dot per region)"]),
      sw("dt", "background:" + css("--wildfire") + ";opacity:.7", "US wildfire"),
      h("span", null, [h("span", { "class": "dash-ring" }), "EMSC-only earthquake"]),
      h("span", null, [h("span", { "class": "ts-icon a-none lg-ts" }, ["TSU"]), "tsunami message"]),
      sw("ring", "", "Copernicus activation")]));
  }

  // Today's reading and tiles (tic-shell): counts from this build, worldwide (the Area menu dims rows, never these
  // counts). An alert is above the bottom rung of its own issuer's scale, in the issuer's words; never Elements' rating.
  // The highest alert in its issuer's words, naming the issuer once (a MeteoAlarm title already carries it).
  // LEAD-BEGIN (tests/test_lead.py runs this block under node)
  // Which alert leads the reading and the Alerts table. The issuer's own rung decides first (never Elements' rating).
  // Within a rung, a fast-onset event (cyclone, earthquake, flood, volcano) comes before a slow-onset one, and only
  // GDACS droughts are slow-onset here: they run for months, so they would otherwise lead on age of report alone.
  // Then the newer report, then the id, so the order is the same on every load.
  function slowOnset(p) { return /^elements:gdacs:DR-/.test(p.id || ""); }
  function leadOrder(x, y, alertOf) {
    var rx = RANK[alertOf(x)[0]] || 0, ry = RANK[alertOf(y)[0]] || 0;
    return ry - rx || (slowOnset(x) ? 1 : 0) - (slowOnset(y) ? 1 : 0)
      || (y.data_as_of || "").localeCompare(x.data_as_of || "") || String(x.id).localeCompare(String(y.id));
  }
  // LEAD-END
  function topLine(p, src) {
    var t = p.title.replace(/^GDACS \w+ alert: /, ""), via = src.split(" via ");
    if (via.length > 1 && t.indexOf(via[0]) >= 0) return t + ", via " + via[1];
    return t + ", " + src;
  }
  function shell(hot, by, fires, health, alertOf) {
    var box = document.getElementById("reading");
    var n = { red: 0, orange: 0, yellow: 0 };
    hot.forEach(function (p) { var c = alertOf(p)[0]; if (c in n) n[c] += 1; });
    var mix = ["red", "orange", "yellow"].filter(function (c) { return n[c]; }).map(function (c) { return num(n[c]) + " " + c; });
    var kids = [h("span", { "class": "tic-reading-k" }, ["Today\u2019s reading"])];
    if (hot.length) {
      var top = hot[0];
      kids.push(h("b", null, [num(hot.length)]), " alert" + (hot.length === 1 ? " is" : "s are") +
        " above the bottom rung of their issuer\u2019s own scale" + (mix.length ? " (" + mix.join(", ") + ")" : "") +
        ". The highest: " + topLine(top, alertOf(top)[1]) + ".");
    } else {
      kids.push("No alert is above the bottom rung of its issuer\u2019s scale in this build.");
    }
    box.replaceChildren.apply(box, kids);
    var srcs = Object.keys(health || {}), up = srcs.filter(function (k) { var s = health[k] || {}; return s.last_ok && !(s.failures > 0); });
    var tiles = [["Alerts above the bottom rung", num(hot.length)], ["Earthquakes M4.5+, past 7 days (USGS)", num(by.usgs.length)],
      ["Fire detections, past 24 hours (FIRMS)", fires && fires.detections !== undefined ? num(fires.detections) : "\u2014"],
      ["Sources reporting", num(up.length) + " of " + num(srcs.length)]];
    document.getElementById("tiles").replaceChildren.apply(document.getElementById("tiles"), tiles.map(function (t) {
      return h("div", { "class": "tile" }, [h("span", { "class": "k" }, [t[0]]), h("span", { "class": "v" }, [t[1]])]); }));
  }

  function lists(feats, health, generated, fires) {
    var by = { usgs: [], gdacs: [], nhc: [], cems: [], firms: [], "usgs-volcano": [], nws: [], spc: [], tsunami: [], usdm: [], meteoalarm: [],
      emsc: [], nifc: [] };
    feats.forEach(function (f) { (by[lane(f)] || []).push(f.properties); });
    var geomOf = {};
    feats.forEach(function (f) { geomOf[f.properties.id] = f.geometry; });
    function mark(row, p) {
      if (A && A.get().kind !== "all" && !inArea({ subdivisions: subsOf(p), countries: p.countries, geometry: geomOf[p.id] }))
        row.cls = "outside";
      return row;
    }

    // Each alert in its own issuer's words: PAGER and GDACS colours, and the USGS aviation colour code for volcanoes.
    function alertOf(p) {
      var ln = lane({ properties: p });
      if (ln === "usgs-volcano") return [(p.measures.aviation_color || "").toLowerCase(), "USGS volcano alert"];
      if (ln === "nws") return [p.measures.severity === "Extreme" ? "red" : "orange", "NWS, " + p.measures.severity.toLowerCase()];
      if (ln === "spc") return [p.measures.level >= 5 ? "red" : "orange", "SPC outlook"];
      if (ln === "tsunami") return [p.measures.level === "warning" ? "red" : "orange", "NOAA tsunami centre"];
      if (ln === "meteoalarm") return [p.measures.awareness_level, (p.measures.issuer || "National weather service") + " via MeteoAlarm"];
      var st = (p.response_stage || ":").split(":");
      return [st[1], st[0] === "pager" ? "USGS PAGER" : "GDACS"];
    }
    var hot = feats.map(function (f) { return f.properties; }).filter(function (p) { return p.tier === "anomaly"; })
      .sort(function (x, y) { return leadOrder(x, y, alertOf); });
    document.getElementById("alerts").replaceChildren(hot.length ? table(["Alert", "Event"], hot.map(function (p) {
      var st = [null, alertOf(p)[0]];
      var what = p.title.replace(/^GDACS \w+ alert: /, "");
      var src = alertOf(p)[1];
      return mark([badge(st[1]), h("span", null, [link(p.link, what), h("span", { "class": "sub" }, [src + " · " + when(p.data_as_of)])])], p); }))
      : empty("No PAGER alert of yellow or worse, no GDACS orange or red alert, no US volcano above Normal, and no Extreme US or red European weather warning."));
    shell(hot, by, fires, health, alertOf);
    var hotCc = [];
    hot.forEach(function (p) { (p.countries || []).forEach(function (c) { if (c && hotCc.indexOf(c) < 0) hotCc.push(c); }); });
    if (window.TicRelated && hotCc.length) TicRelated.render(document.getElementById("tic-related"), { countries: hotCc, here: "elements", level: 2 });

    var vo = by["usgs-volcano"].slice().sort(function (x, y) {
      return (RANK[(y.measures.aviation_color || "").toLowerCase()] || 0) - (RANK[(x.measures.aviation_color || "").toLowerCase()] || 0)
        || x.measures.name.localeCompare(y.measures.name); });
    document.getElementById("volcanoes").replaceChildren(vo.length ? table(["Volcano", "Alert / aviation code", "Change", "Notice"],
      vo.map(function (p) {
        var m = p.measures, prevA = m.previous_alert_level;
        var was = !prevA || prevA === "UNASSIGNED" ? "previously unassigned"
          : m.change ? m.change + " from " + cap(prevA.toLowerCase()) + " / " + cap((m.previous_aviation_color || "").toLowerCase()) : "—";
        return mark([link(p.link, m.name), badge((m.aviation_color || "").toLowerCase(), cap(m.alert_level.toLowerCase()) + " / " + cap((m.aviation_color || "").toLowerCase())),
          was, when(p.data_as_of)], p); }), { 3: 1 })
      : empty("No US volcano is above Normal / Green."));

    var spc = by.spc.slice().sort(function (x, y) { return y.measures.level - x.measures.level; });
    document.getElementById("spc").replaceChildren(spc.length
      ? "SPC Day 1 convective outlook: " + spc.map(function (p) { return p.measures.name + " (" + p.measures.level + " of 5)"; }).join(", ")
        + ", valid until " + when(spc[0].measures.expires) + "."
      : "SPC Day 1 convective outlook: no risk area today (general thunderstorms at most).");
    var wx = by.nws.slice().sort(function (x, y) {
      return (x.measures.severity === "Extreme" ? 0 : 1) - (y.measures.severity === "Extreme" ? 0 : 1)
        || x.measures.event.localeCompare(y.measures.event) || (x.measures.ends || "").localeCompare(y.measures.ends || ""); });
    document.getElementById("nws").replaceChildren(wx.length ? table(["Warning or watch", "Where", "Until", "Office"], wx.map(function (p) {
      var m = p.measures, where = m.areas.length > 3 ? m.areas.slice(0, 3).join("; ") + " and " + (m.areas.length - 3) + " more" : m.areas.join("; ");
      return mark([m.severity === "Extreme" ? badge("red", m.event) : m.event, where, when(m.ends), (m.office || "").replace(/^NWS /, "")], p); }), { 2: 1 })
      : empty("No Severe or Extreme NWS warning or watch is in force."));

    // Europe: orange and red warnings one by one, then every country with a warning in force.
    var euCountry = by.meteoalarm.filter(function (p) { return /:in-force$/.test(p.id); })
      .sort(function (x, y) { var a = x.measures, b = y.measures;
        return (b.red - a.red) || (b.orange - a.orange) || (b.warnings - a.warnings) || a.country_name.localeCompare(b.country_name); });
    var euHot = by.meteoalarm.filter(function (p) { return !/:in-force$/.test(p.id); })
      .sort(function (x, y) { return y.measures.level - x.measures.level || (x.measures.onset || "").localeCompare(y.measures.onset || ""); });
    var euN = euCountry.reduce(function (t, p) { ["warnings", "yellow", "orange", "red"].forEach(function (k) { t[k] += p.measures[k] || 0; }); return t; },
      { warnings: 0, yellow: 0, orange: 0, red: 0 });
    var parts = ["red", "orange", "yellow"].filter(function (k) { return euN[k]; }).map(function (k) { return num(euN[k]) + " " + k; });
    document.getElementById("eu-sum").replaceChildren(euCountry.length
      ? num(euN.warnings) + " warning" + (euN.warnings === 1 ? "" : "s") + " in force in " + euCountry.length + " of MeteoAlarm's 39 countries: " + parts.join(", ") + "."
      : "No yellow, orange or red warning is in force in MeteoAlarm's 39 countries, or MeteoAlarm could not be read (see Sources).");
    document.getElementById("eu-warn").replaceChildren(euHot.length ? table(["Level", "Warning", "Where", "From", "Until"], euHot.map(function (p) {
      var m = p.measures;
      return mark([badge(m.awareness_level, cap(m.awareness_level)), h("span", null, [link(p.link, cap(m.awareness_type)),
        h("span", { "class": "sub" }, [(m.issuer || "") + (m.credit ? " · " + m.credit : "")])]), areaList(m.areas || []), when(m.onset), when(m.expires)], p); }), { 3: 1, 4: 1 })
      : empty("No orange or red warning is in force in Europe."));
    var euCc = document.getElementById("eu-cc");
    if (euCountry.length) {
      euCc.replaceChildren(table(["Country", "Red", "Orange", "Yellow", "Most for"], euCountry.map(function (p) {
        var m = p.measures, top = Object.keys(m.by_type || {})[0];
        return [m.country_name, m.red || "—", m.orange || "—", m.yellow || "—", top ? top + " (" + m.by_type[top] + ")" : "—"]; }), { 1: 1, 2: 1, 3: 1 }));
    } else {
      euCc.replaceChildren();
    }

    var ts = by.tsunami.slice().sort(function (x, y) { return (y.data_as_of || "").localeCompare(x.data_as_of || ""); });
    document.getElementById("tsunami").replaceChildren(ts.length ? table(["Message", "Earthquake", "Sent"], ts.map(function (p) {
      var m = p.measures;
      return mark([link(p.link, cap(TSU[m.level] || m.level) + " (" + m.centre.replace(" Tsunami Warning Center", "") + ")"),
        (m.magnitude != null ? "M" + m.magnitude.toFixed(1) + " " : "") + (m.location || "—"), when(p.data_as_of)], p); }), { 2: 1 })
      : empty("No tsunami message from NOAA's two warning centres in the past 7 days."));

    var dm = by.usdm[0];
    if (dm) {
      var w = dm.measures, pw = w.previous_week;
      var md = w.map_date.split("-"), mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      document.getElementById("drought-sum").replaceChildren("Week of " + Number(md[2]) + " " + mon[Number(md[1]) - 1] + " " + md[0]
        + " (maps are valid on Tuesday and released on Thursday).");
      document.getElementById("drought").replaceChildren(table(["Category", "Share of the US", "Change in a week"], [0, 1, 2, 3, 4].map(function (i) {
        var k = "d" + i, ch = pw ? w[k] - pw[k] : null;
        return [h("span", null, [h("span", { "class": "dmsw", style: "background:" + DM_COLORS[i] }), "D" + i + " " + DM_NAMES[i] + " or worse"]),
          w[k].toFixed(1) + "%", ch == null ? "—" : Math.abs(ch) < 0.05 ? "no change" : (ch > 0 ? "+" : "") + ch.toFixed(1) + " points"]; }), { 1: 1, 2: 1 }));
    } else {
      document.getElementById("drought").replaceChildren(empty("No Drought Monitor data in this build."));
    }

    var bands = [["4.5–4.9", 4.5, 5], ["5.0–5.9", 5, 6], ["6.0–6.9", 6, 7], ["7.0 and above", 7, 99]];
    var counts = bands.map(function (b) { return by.usgs.filter(function (p) { var m = p.measures.magnitude; return m >= b[1] && m < b[2]; }).length; });
    var max = Math.max.apply(null, counts.concat([1]));
    document.getElementById("mags").replaceChildren(h("div", { "class": "bars", "aria-label": "Earthquakes by magnitude" }, bands.reduce(function (acc, b, i) {
      return acc.concat([h("span", null, ["M" + b[0]]),
        h("span", null, [h("div", { "class": "bar", style: "width:" + Math.max(counts[i] ? 2 : 0, 100 * counts[i] / max) + "%" })]),
        h("span", { "class": "num" }, [counts[i]])]); }, [])));
    var big = by.usgs.slice().sort(function (x, y) { return y.measures.magnitude - x.measures.magnitude || (y.data_as_of || "").localeCompare(x.data_as_of || ""); }).slice(0, 10);
    document.getElementById("quakes").replaceChildren(big.length ? table(["Mag.", "Where", "When", "PAGER"], big.map(function (p) {
      var m = p.measures;
      return mark([m.magnitude.toFixed(1), link(p.link, m.place || "—"), when(p.data_as_of), m.pager ? badge(m.pager) : "—"], p); }), { 0: 1, 2: 1 })
      : empty("No earthquakes of magnitude 4.5 or more in the past 7 days."));
    var both = by.usgs.filter(function (p) { return p.measures.emsc && p.measures.emsc.independent; }).length;
    var copy = by.usgs.filter(function (p) { return p.measures.emsc && !p.measures.emsc.independent; }).length;
    document.getElementById("emsc-note").replaceChildren(by.usgs.length
      ? both + " of " + by.usgs.length + " USGS earthquakes are confirmed by EMSC's independent catalogue"
        + (copy ? "; for " + copy + " more, EMSC carries USGS's own solution" : "") + ". "
        + (by.emsc.length ? by.emsc.length + " earthquake" + (by.emsc.length === 1 ? "" : "s") + " of M4.5 or more appear only in EMSC's catalogue (dashed on the map)." : "")
      : "");

    var wf = by.nifc.slice().sort(function (x, y) { return y.measures.acres - x.measures.acres; });
    document.getElementById("wildfires").replaceChildren(wf.length ? table(["Fire", "Where", "Acres", "Contained", "Updated"], wf.slice(0, 15).map(function (p) {
      var m = p.measures;
      return mark([m.name, [m.county ? m.county + " County" : null, m.state].filter(Boolean).join(", "),
        Number(m.acres).toLocaleString("en-US"), m.percent_contained != null ? m.percent_contained + "%" : "—", when(p.data_as_of)], p); }), { 2: 1, 3: 1, 4: 1 })
      : empty("No US wildfire of 100 acres or more is being fought."));

    var tcs = by.gdacs.filter(function (p) { return p.measures.hazard_code === "TC"; })
      .sort(function (x, y) { return (y.measures.to || "").localeCompare(x.measures.to || ""); });
    var rows = by.nhc.map(function (p) {
      var m = p.measures;
      return mark([link(p.link, (NHC[m.classification] || "Storm") + " " + m.name), "NHC advisory", m.intensity_kt + " kt, " + m.pressure_mb + " mb", when(p.data_as_of)], p);
    }).concat(tcs.map(function (p) {
      var m = p.measures, a = (p.response_stage || ":").split(":")[1];
      return mark([link(p.link, (m.name || "").replace(/^Tropical Cyclone /, "")),
        h("span", null, [badge(a), m.latest_alert && m.latest_alert !== a ? h("span", { "class": "small muted" }, [" (latest: " + m.latest_alert + ")"]) : null]),
        (m.severity || "").replace(/^maximum wind /, ""), when(m.to)], p);
    }));
    document.getElementById("cyclones").replaceChildren(rows.length ? table(["Storm", "Alert", "Maximum wind", "Last report"], rows, { 2: 1 })
      : empty("No current tropical cyclone from NHC or GDACS."));

    var cems = by.cems.slice().sort(function (x, y) { return (y.measures.activated || "").localeCompare(x.measures.activated || ""); });
    document.getElementById("cems").replaceChildren(cems.length ? table(["Code", "Event", "Activated", "Maps", "Status"], cems.map(function (p) {
      var m = p.measures;
      return mark([link(p.link, m.code), m.name || "—", when(m.activated), m.products != null ? m.products : "—", m.closed ? "closed" : "open"], p); }), { 2: 1, 3: 1 })
      : empty("No Copernicus EMS activation is open or less than 60 days old."));

    var grid = {};
    by.gdacs.forEach(function (p) {
      var hz = p.measures.hazard, a = (p.response_stage || ":").split(":")[1] || "none";
      grid[hz] = grid[hz] || { green: 0, orange: 0, red: 0 };
      grid[hz][a] = (grid[hz][a] || 0) + 1;
    });
    var hz = Object.keys(grid).sort(function (a, b) {
      return (grid[b].red * 100 + grid[b].orange * 10 + grid[b].green) - (grid[a].red * 100 + grid[a].orange * 10 + grid[a].green); });
    document.getElementById("gdacs").replaceChildren(hz.length ? table(["Hazard", "Green", "Orange", "Red"], hz.map(function (k) {
      return [(HAZ[k] || [0, cap(k)])[1], grid[k].green || "—", grid[k].orange || "—", grid[k].red || "—"]; }), { 1: 1, 2: 1, 3: 1 })
      : empty("GDACS lists no current alerts."));

    // Every GDACS alert beside the map, green included, strongest first and then newest.
    function showOnMap(id) {
      var mk = gdMarkers[id], box = document.querySelector('.layers input[data-layer="gdacs"]');
      if (!mk) return;
      if (box && !box.checked) { box.checked = true; box.dispatchEvent(new Event("change")); }
      map.setView(mk.getLatLng(), Math.max(map.getZoom(), 4));
      mk.openTooltip();
      document.getElementById("map").scrollIntoView({ block: "nearest" });
    }
    var gdRows = by.gdacs.slice().sort(function (x, y) {
      var ax = (x.response_stage || ":").split(":")[1], ay = (y.response_stage || ":").split(":")[1];
      return (RANK[ay] || 0) - (RANK[ax] || 0) || (y.measures.to || "").localeCompare(x.measures.to || "");
    }).map(function (p) {
      var m = p.measures, a = (p.response_stage || ":").split(":")[1], name = p.title.replace(/^GDACS \w+ alert: /, "");
      var btn = gdMarkers[p.id] ? h("button", { type: "button", "class": "gd-show", "aria-label": "Show " + name + " on the map" }, ["Map"]) : "—";
      if (btn instanceof Node) btn.addEventListener("click", function () { showOnMap(p.id); });
      var title = link(p.link, name);
      if (title instanceof Node) title.title = name;  // beside the map a long name is cut to two lines
      return mark([badge(a), h("span", null, [title,
        h("span", { "class": "sub" }, [when(m.from) + " to " + when(m.to)
          + (m.latest_alert && m.latest_alert !== a ? " · latest episode: " + m.latest_alert : "")])]), btn], p);
    });
    var gdList = gdRows.length ? table(["Alert", "Event", "Map"], gdRows) : empty("GDACS lists no current alerts.");
    if (gdRows.length) gdList.id = "gd-list-table";
    document.getElementById("gd-count").textContent = gdRows.length ? " (" + gdRows.length + ")" : "";
    document.getElementById("gd-list").replaceChildren(gdList);

    var fz = by.firms.slice().sort(function (x, y) { return y.measures.detections - x.measures.detections; });
    var fsum = document.getElementById("fires-sum");
    if (fires && fires.cells && fires.cells.length) {
      var SAT = { VIIRS_NOAA20_NRT: "NOAA-20", VIIRS_NOAA21_NRT: "NOAA-21", VIIRS_SNPP_NRT: "Suomi-NPP" };
      var vk = Object.keys(fires.via || {});
      var pub = vk.some(function (k) { return fires.via[k].indexOf("public files") === 0; });
      var none = vk.filter(function (k) { return / \(no rows\)$/.test(fires.via[k]); }).map(function (k) { return SAT[k] || k; });
      fsum.replaceChildren(num(fires.detections) + " detections in " + num(fires.cells.length) + " half-degree cells, "
        + when(fires.window[0]) + " to " + when(fires.window[1]) + "; newest " + when(fires.newest)
        + (pub ? " (FIRMS public files, about three hours behind)" : " (FIRMS API)") + "."
        + (none.length ? " No detections from " + none.join(" or ") + " in this read." : ""));
    } else {
      fsum.replaceChildren("No FIRMS data in this build.");
    }
    document.getElementById("fires").replaceChildren(fz.length ? table(["Country", "Detections", "High confidence", "Radiative power (MW)"],
      fz.slice(0, 15).map(function (p) {
        var m = p.measures;
        return [m.country_name, num(m.detections), num(m.high_confidence), num(Math.round(m.frp_sum_mw))]; }), { 1: 1, 2: 1, 3: 1 })
      : empty("No country had 10 or more detections in the past 24 hours."));

    var names = { "usgs-earthquakes": "USGS earthquakes (M4.5+, past 7 days)", gdacs: "GDACS alerts (current events)",
      nhc: "NOAA National Hurricane Center", "copernicus-ems": "Copernicus EMS rapid mapping",
      "nasa-firms": "NASA FIRMS (VIIRS, past 24 hours)", "usgs-volcanoes": "USGS volcano alerts (US volcanoes)",
      "nws-alerts": "NWS alerts (Severe and Extreme)", "spc-outlook": "SPC Day 1 convective outlook",
      "noaa-tsunami": "NOAA tsunami warning centres", "us-drought-monitor": "US Drought Monitor (weekly)",
      meteoalarm: "MeteoAlarm warnings (39 European countries)", emsc: "EMSC earthquakes (M4.5+, past 7 days)",
      "nifc-wfigs": "NIFC wildfire incidents (WFIGS)" };
    document.getElementById("health").replaceChildren(table(["Source", "Last good", "Status"], Object.keys(names).map(function (k) {
      var s = health[k] || {};
      var bad = !s.last_ok || (s.failures || 0) > 0;
      return [names[k], when(s.last_ok), h("span", { "class": bad ? "bad" : "ok" }, [s.detail || "no data"])]; }), { 1: 1 }));

    document.getElementById("asof").setAttribute("datetime", generated);
    T.renderAll(document);
  }

  T.mountSettings(document.getElementById("time-settings"));
  function get(u) {
    return fetch(u, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });
  }
  // The fire cells are optional: without them the rest of the page still draws.
  Promise.all([get("geo/world.json"), get("data/feed.geojson"), get("data/health.json"),
    get("data/fires.json").catch(function () { return null; }), get("data/drought.json").catch(function () { return null; }),
    get("data/meteoalarm.json").catch(function () { return null; }),
    get("data/wildfires.json").catch(function () { return null; }),
    get("geo/states.json").catch(function () { return null; })]).then(function (x) {
    if (A && x[7]) {
      A.mountSettings(document.getElementById("area-settings"), x[7].states, { note: "Hazards tied to a place outside " +
        "your area are dimmed on the map and in the tables, not hidden. Summaries by country are never dimmed. Saved in " +
        "this browser only; your location is never sent anywhere." });
    } else {
      A = null;  // no state list in this build: no Area menu, nothing dimmed
    }
    draw(x[0], x[1].features, x[3], x[4], x[5], x[6] && x[6].fires);
    lists(x[1].features, x[2], x[1].generated_at, x[3]);
    dim(x[1].features);
    T.onChange(function () { lists(x[1].features, x[2], x[1].generated_at, x[3]); });
    if (A) A.onChange(function () { lists(x[1].features, x[2], x[1].generated_at, x[3]); dim(x[1].features); });
  }).catch(function (e) {
    document.getElementById("map").replaceChildren(h("p", { "class": "empty", style: "padding:16px" }, ["The data could not be loaded (" + e.message + ")."]));
  });
})();
