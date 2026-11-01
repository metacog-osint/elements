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
  function table(head, rows, numCols) {
    numCols = numCols || {};
    return h("table", null, [h("thead", null, [h("tr", null, head.map(function (x, i) { return h("th", { "class": numCols[i] ? "num" : null }, [x]); }))]),
      h("tbody", null, rows.map(function (r) { return h("tr", null, r.map(function (c, i) {
        return h("td", { "class": numCols[i] ? "num" : null }, [c]); })); }))]);
  }
  function empty(text) { return h("p", { "class": "empty" }, [text]); }
  function alertColor(a) { return a && RANK[a] != null ? css("--a-" + a) : css("--unrated"); }
  function badge(a, label) { return h("span", { "class": "badge a-" + (a || "none") }, [label || a || "none"]); }
  function lane(f) { return f.properties.id.split(":")[1]; }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  // Wheel zoom stays off until the reader clicks the map, so scrolling the page never gets trapped in it.
  // The opening view fits the whole world's width, so the Pacific (Alaska, Hawaii, the Aleutian and Tonga trenches) is in view.
  var map = L.map("map", { worldCopyJump: true, minZoom: 1, maxZoom: 8, zoomSnap: 0.25, scrollWheelZoom: false })
    .fitBounds([[-55, -180], [75, 180]]);
  map.once("click", function () { map.scrollWheelZoom.enable(); });
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution("Natural Earth · USGS · GDACS · NOAA NHC · Copernicus EMS · NASA FIRMS");
  // (USGS covers both the earthquake and the volcano layers.)
  var layers = {};

  function quakeRadius(m) { return Math.max(3, 3 + (m - 4.5) * 2.6); }
  var FIRE_BREAKS = [[100, "100+"], [20, "20–99"], [5, "5–19"], [1, "1–4"]];
  function fireStep(n) { return n >= 100 ? 4 : n >= 20 ? 3 : n >= 5 ? 2 : 1; }
  function num(n) { return Number(n).toLocaleString("en-US"); }

  function draw(world, feats, fires) {
    // Land goes in its own pane below the overlays: Leaflet stacks any SVG above any canvas in a pane, and the fire
    // canvas has to sit above the land.
    map.createPane("land").style.zIndex = 350;
    L.geoJSON(world, { pane: "land", interactive: false,
      style: { color: css("--border"), weight: 0.6, fillColor: css("--land"), fillOpacity: 1 } }).addTo(map);
    var by = { usgs: [], gdacs: [], nhc: [], cems: [], "usgs-volcano": [] };
    feats.forEach(function (f) { (by[lane(f)] || []).push(f); });

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
      dots.push(dot);
      dot
        .bindTooltip(tip(num(c[2]) + " fire and heat detections" + (c[3] ? " (" + num(c[3]) + " high confidence)" : "")
          + "\nRadiative power " + num(c[4]) + " MW in all, largest " + num(c[5]) + " MW"
          + "\n" + (c[7] ? names[c[7]] || c[7] : "At sea or unassigned") + "\nLatest " + when(c[6])), { sticky: true })
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
        L.circleMarker([c[1], c[0]], { radius: quakeRadius(m.magnitude), weight: 1, color: css("--mark-edge"),
          fillColor: alertColor(m.pager), fillOpacity: m.pager ? 0.9 : 0.55 })
          .bindTooltip(tip(f.properties.title + "\n" + when(f.properties.data_as_of) + (m.depth_km != null ? ", depth " + m.depth_km + " km" : "")
            + (m.pager ? "\nPAGER " + m.pager : "\nNo PAGER alert issued")
            + (m.tsunami_flag ? "\nUSGS tsunami flag set (a large ocean event; it does not mean a tsunami occurred)" : "")))
          .addTo(layers.usgs);
      });
    layers.usgs.addTo(map);

    layers.gdacs = L.layerGroup();
    function gdAlert(f) { return (f.properties.response_stage || ":").split(":")[1]; }
    // Higher alerts drawn last, so they sit on top; green icons are smaller so they don't crowd out the rest.
    by.gdacs.slice().sort(function (a, b) { return (RANK[gdAlert(a)] || 0) - (RANK[gdAlert(b)] || 0); })
      .forEach(function (f) {
        if (!f.geometry) return;
        var p = f.properties, m = p.measures, c = f.geometry.coordinates;
        var a = (p.response_stage || "").split(":")[1];
        var code = (HAZ[m.hazard] || ["?"])[0];
        L.marker([c[1], c[0]], { keyboard: true, title: p.title,
          zIndexOffset: 100 * (RANK[a] || 0),
          icon: L.divIcon({ className: "gd-icon a-" + (a || "none"), html: "", iconSize: RANK[a] >= 2 ? [26, 19] : [19, 14] }) })
          .bindTooltip(tip(p.title + "\n" + when(m.from) + " to " + when(m.to)
            + (m.latest_alert && m.latest_alert !== a ? "\nLatest episode: " + m.latest_alert : "")))
          .on("add", function (ev) { ev.target.getElement().textContent = code; })
          .addTo(layers.gdacs);
      });
    layers.gdacs.addTo(map);

    layers.nhc = L.layerGroup();
    by.nhc.forEach(function (f) {
      if (!f.geometry) return;
      var m = f.properties.measures, c = f.geometry.coordinates;
      L.marker([c[1], c[0]], { keyboard: true, title: f.properties.title,
        icon: L.divIcon({ className: "nhc-icon", html: "", iconSize: [26, 26] }) })
        .bindTooltip(tip(f.properties.title + "\nMoving " + (m.movement || "—") + "\nAdvisory " + when(f.properties.data_as_of)))
        .on("add", function (ev) { ev.target.getElement().textContent = m.classification || "TC"; })
        .addTo(layers.nhc);
    });
    layers.nhc.addTo(map);

    layers.volcano = L.layerGroup();
    by["usgs-volcano"].forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties, m = p.measures, c = f.geometry.coordinates;
      var col = (m.aviation_color || "").toLowerCase();
      L.marker([c[1], c[0]], { keyboard: true, title: p.title, zIndexOffset: 400,
        icon: L.divIcon({ className: "vo-icon a-" + (col || "none"), html: "", iconSize: [18, 16] }) })
        .bindTooltip(tip(p.title + "\n" + (m.synopsis || "") + "\n" + (m.observatory || "USGS") + ", " + when(p.data_as_of)
          + (m.nvews_threat ? "\nUSGS threat ranking: " + m.nvews_threat : "")))
        .addTo(layers.volcano);
    });
    layers.volcano.addTo(map);

    layers.cems = L.layerGroup();
    by.cems.forEach(function (f) {
      if (!f.geometry) return;
      var p = f.properties, m = p.measures, c = f.geometry.coordinates;
      L.circleMarker([c[1], c[0]], { radius: 7, weight: 2.2, color: css("--cems"), fill: true, fillOpacity: 0, dashArray: m.closed ? "3 3" : null })
        .bindTooltip(tip(p.title + "\n" + (m.category || "") + ", activated " + when(m.activated) + (m.closed ? " (closed)" : " (open)")))
        .addTo(layers.cems);
    });
    layers.cems.addTo(map);

    document.querySelectorAll(".layers input").forEach(function (box) {
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
      h("span", null, [h("span", { "class": "gd-icon a-orange lg-icon" }, ["FL"]), "GDACS hazard"]),
      h("span", null, [h("span", { "class": "vo-icon a-orange lg-vo" }), "US volcano (aviation code)"]),
      sw("ring", "", "Copernicus activation")]));
  }

  function lists(feats, health, generated, fires) {
    var by = { usgs: [], gdacs: [], nhc: [], cems: [], firms: [], "usgs-volcano": [] };
    feats.forEach(function (f) { (by[lane(f)] || []).push(f.properties); });

    // Each alert in its own issuer's words: PAGER and GDACS colours, and the USGS aviation colour code for volcanoes.
    function alertOf(p) {
      if (lane({ properties: p }) === "usgs-volcano") return [(p.measures.aviation_color || "").toLowerCase(), "USGS volcano alert"];
      var st = (p.response_stage || ":").split(":");
      return [st[1], st[0] === "pager" ? "USGS PAGER" : "GDACS"];
    }
    var hot = feats.map(function (f) { return f.properties; }).filter(function (p) { return p.tier === "anomaly"; })
      .sort(function (x, y) {
        var rx = RANK[alertOf(x)[0]] || 0, ry = RANK[alertOf(y)[0]] || 0;
        return ry - rx || (y.data_as_of || "").localeCompare(x.data_as_of || "");
      });
    document.getElementById("alerts").replaceChildren(hot.length ? table(["Alert", "Event"], hot.map(function (p) {
      var st = [null, alertOf(p)[0]];
      var what = p.title.replace(/^GDACS \w+ alert: /, "");
      var src = alertOf(p)[1];
      return [badge(st[1]), h("span", null, [link(p.link, what), h("span", { "class": "sub" }, [src + " · " + when(p.data_as_of)])])]; }))
      : empty("No PAGER alert of yellow or worse, no GDACS orange or red alert, and no US volcano above Normal."));

    var vo = by["usgs-volcano"].slice().sort(function (x, y) {
      return (RANK[(y.measures.aviation_color || "").toLowerCase()] || 0) - (RANK[(x.measures.aviation_color || "").toLowerCase()] || 0)
        || x.measures.name.localeCompare(y.measures.name); });
    document.getElementById("volcanoes").replaceChildren(vo.length ? table(["Volcano", "Alert / aviation code", "Change", "Notice"],
      vo.map(function (p) {
        var m = p.measures, prevA = m.previous_alert_level;
        var was = !prevA || prevA === "UNASSIGNED" ? "previously unassigned"
          : m.change ? m.change + " from " + cap(prevA.toLowerCase()) + " / " + cap((m.previous_aviation_color || "").toLowerCase()) : "—";
        return [link(p.link, m.name), badge((m.aviation_color || "").toLowerCase(), cap(m.alert_level.toLowerCase()) + " / " + cap((m.aviation_color || "").toLowerCase())),
          was, when(p.data_as_of)]; }), { 3: 1 })
      : empty("No US volcano is above Normal / Green."));

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
      return [m.magnitude.toFixed(1), link(p.link, m.place || "—"), when(p.data_as_of), m.pager ? badge(m.pager) : "—"]; }), { 0: 1, 2: 1 })
      : empty("No earthquakes of magnitude 4.5 or more in the past 7 days."));

    var tcs = by.gdacs.filter(function (p) { return p.measures.hazard_code === "TC"; })
      .sort(function (x, y) { return (y.measures.to || "").localeCompare(x.measures.to || ""); });
    var rows = by.nhc.map(function (p) {
      var m = p.measures;
      return [link(p.link, (NHC[m.classification] || "Storm") + " " + m.name), "NHC advisory", m.intensity_kt + " kt, " + m.pressure_mb + " mb", when(p.data_as_of)];
    }).concat(tcs.map(function (p) {
      var m = p.measures, a = (p.response_stage || ":").split(":")[1];
      return [link(p.link, (m.name || "").replace(/^Tropical Cyclone /, "")),
        h("span", null, [badge(a), m.latest_alert && m.latest_alert !== a ? h("span", { "class": "small muted" }, [" (latest: " + m.latest_alert + ")"]) : null]),
        (m.severity || "").replace(/^maximum wind /, ""), when(m.to) + (m.current ? " (GDACS: current)" : "")];
    }));
    document.getElementById("cyclones").replaceChildren(rows.length ? table(["Storm", "Alert", "Maximum wind", "Last report"], rows, { 2: 1 })
      : empty("No tropical cyclones reported in the past 14 days."));

    var cems = by.cems.slice().sort(function (x, y) { return (y.measures.activated || "").localeCompare(x.measures.activated || ""); });
    document.getElementById("cems").replaceChildren(cems.length ? table(["Code", "Event", "Activated", "Maps", "Status"], cems.map(function (p) {
      var m = p.measures;
      return [link(p.link, m.code), m.name || "—", when(m.activated), m.products != null ? m.products : "—", m.closed ? "closed" : "open"]; }), { 2: 1, 3: 1 })
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
      : empty("GDACS listed no alerts in the past 14 days."));

    var fz = by.firms.slice().sort(function (x, y) { return y.measures.detections - x.measures.detections; });
    var fsum = document.getElementById("fires-sum");
    if (fires && fires.cells && fires.cells.length) {
      var via = Object.keys(fires.via || {}).map(function (k) { return fires.via[k]; });
      fsum.replaceChildren(num(fires.detections) + " detections in " + num(fires.cells.length) + " half-degree cells, "
        + when(fires.window[0]) + " to " + when(fires.window[1]) + "; newest " + when(fires.newest)
        + (via.indexOf("public files") >= 0 ? " (FIRMS public files, about three hours behind)" : " (FIRMS API)") + ".");
    } else {
      fsum.replaceChildren("No FIRMS data in this build.");
    }
    document.getElementById("fires").replaceChildren(fz.length ? table(["Country", "Detections", "High confidence", "Radiative power (MW)"],
      fz.slice(0, 15).map(function (p) {
        var m = p.measures;
        return [m.country_name, num(m.detections), num(m.high_confidence), num(Math.round(m.frp_sum_mw))]; }), { 1: 1, 2: 1, 3: 1 })
      : empty("No country had 10 or more detections in the past 24 hours."));

    var names = { "usgs-earthquakes": "USGS earthquakes (M4.5+, past 7 days)", gdacs: "GDACS alerts (past 14 days)",
      nhc: "NOAA National Hurricane Center", "copernicus-ems": "Copernicus EMS rapid mapping",
      "nasa-firms": "NASA FIRMS (VIIRS, past 24 hours)", "usgs-volcanoes": "USGS volcano alerts (US volcanoes)" };
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
    get("data/fires.json").catch(function () { return null; })]).then(function (x) {
    draw(x[0], x[1].features, x[3]);
    lists(x[1].features, x[2], x[1].generated_at, x[3]);
    T.onChange(function () { lists(x[1].features, x[2], x[1].generated_at, x[3]); });
  }).catch(function (e) {
    document.getElementById("map").replaceChildren(h("p", { "class": "empty", style: "padding:16px" }, ["The data could not be loaded (" + e.message + ")."]));
  });
})();
