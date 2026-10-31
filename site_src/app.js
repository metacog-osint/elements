/* Elements map page. Reads data/feed.geojson (the program's tic-feed/2 feed, built by tools/elements.py),
 * data/health.json and geo/world.json (Natural Earth outlines). Text is inserted as text, never HTML. Times go
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
  var map = L.map("map", { worldCopyJump: true, minZoom: 1, maxZoom: 8, zoomSnap: 0.5, scrollWheelZoom: false })
    .setView([18, 20], 2);
  map.once("click", function () { map.scrollWheelZoom.enable(); });
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution("Natural Earth · USGS · GDACS · NOAA NHC · Copernicus EMS");
  var layers = {};

  function quakeRadius(m) { return Math.max(3, 3 + (m - 4.5) * 2.6); }

  function draw(world, feats) {
    L.geoJSON(world, { interactive: false,
      style: { color: css("--border"), weight: 0.6, fillColor: css("--land"), fillOpacity: 1 } }).addTo(map);
    var by = { usgs: [], gdacs: [], nhc: [], cems: [] };
    feats.forEach(function (f) { (by[lane(f)] || []).push(f); });

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
    document.getElementById("legend").replaceChildren(
      h("span", { "class": "lg-h" }, ["Alert:"]),
      sw("dt", "background:" + css("--a-green"), "green"), sw("dt", "background:" + css("--a-yellow"), "yellow"),
      sw("dt", "background:" + css("--a-orange"), "orange"), sw("dt", "background:" + css("--a-red"), "red"),
      sw("dt", "background:" + css("--unrated") + ";opacity:.6", "no PAGER alert"),
      h("span", null, ["Circle size: magnitude"]),
      h("span", null, [h("span", { "class": "gd-icon a-orange lg-icon" }, ["FL"]), "GDACS hazard"]),
      sw("ring", "", "Copernicus activation"));
  }

  function lists(feats, health, generated) {
    var by = { usgs: [], gdacs: [], nhc: [], cems: [] };
    feats.forEach(function (f) { (by[lane(f)] || []).push(f.properties); });

    var hot = feats.map(function (f) { return f.properties; }).filter(function (p) { return p.tier === "anomaly"; })
      .sort(function (x, y) {
        var rx = RANK[(x.response_stage || "").split(":")[1]] || 0, ry = RANK[(y.response_stage || "").split(":")[1]] || 0;
        return ry - rx || (y.data_as_of || "").localeCompare(x.data_as_of || "");
      });
    document.getElementById("alerts").replaceChildren(hot.length ? table(["Alert", "Event"], hot.map(function (p) {
      var st = (p.response_stage || ":").split(":");
      var what = p.title.replace(/^GDACS \w+ alert: /, "");
      var src = st[0] === "pager" ? "USGS PAGER" : "GDACS";
      return [badge(st[1]), h("span", null, [link(p.link, what), h("span", { "class": "sub" }, [src + " · " + when(p.data_as_of)])])]; }))
      : empty("No PAGER alert of yellow or worse, and no GDACS orange or red alert, in the collection window."));

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

    var names = { "usgs-earthquakes": "USGS earthquakes (M4.5+, past 7 days)", gdacs: "GDACS alerts (past 14 days)",
      nhc: "NOAA National Hurricane Center", "copernicus-ems": "Copernicus EMS rapid mapping" };
    document.getElementById("health").replaceChildren(table(["Source", "Last good", "Status"], Object.keys(names).map(function (k) {
      var s = health[k] || {};
      var bad = !s.last_ok || (s.failures || 0) > 0;
      return [names[k], when(s.last_ok), h("span", { "class": bad ? "bad" : "ok" }, [s.detail || "no data"])]; }), { 1: 1 }));

    document.getElementById("asof").setAttribute("datetime", generated);
    T.renderAll(document);
  }

  T.mountSettings(document.getElementById("time-settings"));
  Promise.all(["geo/world.json", "data/feed.geojson", "data/health.json"].map(function (u) {
    return fetch(u, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });
  })).then(function (x) {
    draw(x[0], x[1].features);
    lists(x[1].features, x[2], x[1].generated_at);
    T.onChange(function () { lists(x[1].features, x[2], x[1].generated_at); });
  }).catch(function (e) {
    document.getElementById("map").replaceChildren(h("p", { "class": "empty", style: "padding:16px" }, ["The data could not be loaded (" + e.message + ")."]));
  });
})();
