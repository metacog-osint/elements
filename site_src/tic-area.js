/*! tic-area.js v1.1 (Cordon 15 Nov 2026; Elements 16 Nov 2026: per-site note) · "My area": each viewer picks the part of the world they care about,
 * saved in this browser only. Places outside it are dimmed, never hidden. Written to move into the hub's shared/
 * folder beside tic-time.js once a second site uses it. Uses tic-time.css for its dialog.
 *
 *    TicArea.mountSettings(el, states, opts)  adds an "Area" button; states = [{code: "US-ND", name, boxes: [[w,s,e,n], ...]}];
 *                                       opts.note replaces the dialog's closing note (v1.1)
 *    TicArea.get()                      {kind: "all"|"conus"|"state"|"near", code?, lat?, lon?, km?}
 *    TicArea.contains(item)             true or false; item = {subdivisions, countries, geometry}; countries
 *                                       without "US" put an item outside any US state or the US 48 (v1.1)
 *    TicArea.label()                    the area in words ("North Dakota", "within 150 km of 46.88, -96.79")
 *    TicArea.onChange(fn)
 */
(function () {
  "use strict";
  var KEY = "tic-area-v1";
  var OUTSIDE_48 = { "US-AK": 1, "US-HI": 1 };
  var states = [], byCode = {}, conusBox = null, listeners = [];

  function clean(a) {
    a = a || {};
    if (a.kind === "conus") return { kind: "conus" };
    if (a.kind === "state" && /^[A-Z]{2}-[A-Z0-9]{1,3}$/.test(a.code || "")) return { kind: "state", code: a.code };
    var lat = Number(a.lat), lon = Number(a.lon), km = Number(a.km);
    if (a.kind === "near" && isFinite(lat) && isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 && km > 0 && km <= 5000)
      return { kind: "near", lat: lat, lon: lon, km: km };
    return { kind: "all" };
  }
  var current = { kind: "all" };
  try { current = clean(JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) { current = { kind: "all" }; }
  function save(a) {
    current = clean(a);
    try { localStorage.setItem(KEY, JSON.stringify(current)); } catch (e) { /* private window: this visit only */ }
    listeners.forEach(function (fn) { try { fn(current); } catch (e) { /* one listener must not stop the rest */ } });
  }

  function walk(c, out) {
    if (typeof c[0] === "number") { out.push(c); return; }
    for (var i = 0; i < c.length; i++) walk(c[i], out);
  }
  function positions(g) {
    var out = [];
    if (!g) return out;
    if (g.type === "GeometryCollection") (g.geometries || []).forEach(function (x) { out = out.concat(positions(x)); });
    else if (g.coordinates) walk(g.coordinates, out);
    return out;
  }
  function boxOf(g) {
    var p = positions(g);
    if (!p.length) return null;
    var b = [Infinity, Infinity, -Infinity, -Infinity];
    p.forEach(function (q) { b[0] = Math.min(b[0], q[0]); b[1] = Math.min(b[1], q[1]); b[2] = Math.max(b[2], q[0]); b[3] = Math.max(b[3], q[1]); });
    return b;
  }
  function pointsOnly(g) {
    if (!g) return false;
    if (g.type === "GeometryCollection") return (g.geometries || []).every(pointsOnly);
    return g.type === "Point" || g.type === "MultiPoint";
  }
  function rings(g) {
    if (!g) return [];
    if (g.type === "Polygon") return [g.coordinates[0]];
    if (g.type === "MultiPolygon") return g.coordinates.map(function (p) { return p[0]; });
    if (g.type === "GeometryCollection") return (g.geometries || []).reduce(function (a, x) { return a.concat(rings(x)); }, []);
    return [];
  }
  function inRing(x, y, r) {
    var inside = false;
    for (var i = 0, j = r.length - 1; i < r.length; j = i++) {
      if ((r[i][1] > y) !== (r[j][1] > y) && x < (r[j][0] - r[i][0]) * (y - r[i][1]) / (r[j][1] - r[i][1]) + r[i][0]) inside = !inside;
    }
    return inside;
  }
  function inBox(q, b) { return q[0] >= b[0] && q[0] <= b[2] && q[1] >= b[1] && q[1] <= b[3]; }
  function meets(a, b) { return a && b && a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]; }
  function km(lat1, lon1, lat2, lon2) {
    var r = Math.PI / 180, dl = (lat2 - lat1) * r, dn = (lon2 - lon1) * r;
    var h = Math.sin(dl / 2) * Math.sin(dl / 2) + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dn / 2) * Math.sin(dn / 2);
    return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  /* An item is in the area when its program placed it in a chosen state (its `subdivisions`); an item whose
   * `countries` leave out the US is outside any US state or the US 48 (v1.1: a flood in Mexico inside the US 48's box);
   * failing that, when one of its points lies in the area's box, or (for an area or line) its box meets the area's box: a warning at sea
   * off the coast. A "near" area takes any of its points within the distance, or a polygon around the centre. A set
   * of scattered points (drilling rigs, radio sites) is never judged by the box around all of them. */
  function contains(item) {
    var a = current;
    if (!item || a.kind === "all") return true;
    var subs = item.subdivisions || [];
    var g = item.geometry || null;
    if (a.kind === "near") {
      var p = positions(g);
      if (!p.length) return false;
      if (p.some(function (q) { return km(a.lat, a.lon, q[1], q[0]) <= a.km; })) return true;
      return rings(g).some(function (r) { return inRing(a.lon, a.lat, r); });
    }
    function placed(boxes) {
      if (pointsOnly(g)) return positions(g).some(function (q) { return boxes.some(function (b) { return inBox(q, b); }); });
      var ib = boxOf(g);
      return boxes.some(function (b) { return meets(ib, b); });
    }
    var cc = item.countries || [];
    if ((a.kind === "state" || a.kind === "conus") && cc.length && cc.indexOf("US") < 0) return false;
    if (a.kind === "state") {
      if (subs.length) return subs.indexOf(a.code) >= 0;
      return placed((byCode[a.code] || {}).boxes || []);
    }
    if (a.kind === "conus") {
      if (subs.length) return subs.some(function (s) { return s.indexOf("US-") === 0 && !OUTSIDE_48[s]; });
      return conusBox ? placed([conusBox]) : false;
    }
    return true;
  }
  function label(a) {
    a = a || current;
    if (a.kind === "conus") return "the contiguous United States";
    if (a.kind === "state") return (byCode[a.code] || {}).name || a.code;
    if (a.kind === "near") return "within " + a.km + " km of " + a.lat.toFixed(2) + ", " + a.lon.toFixed(2);
    return "everywhere";
  }

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (k) { e.append(k); });
    return e;
  }
  var NOTE = "Notices tied to a place outside your area are dimmed, not hidden. Travel advice for other countries is " +
    "never dimmed. Saved in this browser only; your location is never sent anywhere.";
  function mountSettings(container, list, opts) {
    states = (list || []).slice().sort(function (x, y) { return x.name.localeCompare(y.name); });
    byCode = {};
    conusBox = null;
    states.forEach(function (s) {
      byCode[s.code] = s;
      if (!OUTSIDE_48[s.code] && s.code.indexOf("US-") === 0) {
        (s.boxes || []).forEach(function (b) {
          conusBox = conusBox ? [Math.min(conusBox[0], b[0]), Math.min(conusBox[1], b[1]),
            Math.max(conusBox[2], b[2]), Math.max(conusBox[3], b[3])] : b.slice();
        });
      }
    });
    var btn = el("button", { type: "button", "class": "tic-time-btn", "aria-haspopup": "dialog", title: "Your area of interest" }, ["Area"]);
    var dlg = el("dialog", { "class": "tic-time-dialog", "aria-label": "Area settings" });
    var sel = el("select", { id: "tic-area-kind" });
    sel.append(el("option", { value: "all" }, ["Everywhere (nothing dimmed)"]), el("option", { value: "conus" }, ["Contiguous United States"]));
    states.forEach(function (s) { sel.append(el("option", { value: "state:" + s.code }, [s.name])); });
    sel.append(el("option", { value: "near" }, ["Within a distance of a point…"]));
    var lat = el("input", { id: "tic-area-lat", type: "text", inputmode: "decimal", placeholder: "46.88", size: "8" });
    var lon = el("input", { id: "tic-area-lon", type: "text", inputmode: "decimal", placeholder: "-96.79", size: "8" });
    var dist = el("input", { id: "tic-area-km", type: "text", inputmode: "numeric", placeholder: "150", size: "5" });
    var here = el("button", { type: "button" }, ["Use my location"]);
    var nearRow = el("fieldset", { "class": "tic-time-row" }, [el("legend", null, ["Point and distance"]),
      el("label", { "for": "tic-area-lat" }, ["Latitude ", lat]), el("label", { "for": "tic-area-lon" }, ["Longitude ", lon]),
      el("label", { "for": "tic-area-km" }, ["Km ", dist]), here]);
    var msg = el("p", { "class": "tic-time-msg", role: "alert" });
    var done = el("button", { type: "button", "class": "tic-time-done" }, ["Done"]);
    var cancel = el("button", { type: "button" }, ["Cancel"]);
    dlg.append(el("h2", null, ["Your area"]),
      el("p", { "class": "tic-time-row" }, [el("label", { "for": "tic-area-kind" }, ["Area "]), sel]), nearRow, msg,
      el("p", { "class": "tic-time-actions" }, [cancel, done]),
      el("p", { "class": "tic-time-note" }, [(opts && opts.note) || NOTE]));
    function show() {
      var a = current;
      sel.value = a.kind === "state" ? "state:" + a.code : a.kind;
      lat.value = a.kind === "near" ? a.lat : ""; lon.value = a.kind === "near" ? a.lon : ""; dist.value = a.kind === "near" ? a.km : "";
      nearRow.hidden = sel.value !== "near";
      msg.textContent = "";
    }
    sel.addEventListener("change", function () { nearRow.hidden = sel.value !== "near"; msg.textContent = ""; });
    here.addEventListener("click", function () {
      if (!navigator.geolocation) { msg.textContent = "This browser cannot give a location; type the point instead."; return; }
      navigator.geolocation.getCurrentPosition(function (p) {
        lat.value = p.coords.latitude.toFixed(3); lon.value = p.coords.longitude.toFixed(3);
        if (!dist.value) dist.value = "150";
      }, function () { msg.textContent = "No location was given; type the point instead."; }, { maximumAge: 600000, timeout: 10000 });
    });
    btn.addEventListener("click", function () { show(); if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", ""); });
    cancel.addEventListener("click", function () { dlg.close(); });
    done.addEventListener("click", function () {
      var v = sel.value, next;
      if (v.indexOf("state:") === 0) next = { kind: "state", code: v.slice(6) };
      else if (v === "near") {
        next = clean({ kind: "near", lat: lat.value, lon: lon.value, km: dist.value || 150 });
        if (next.kind !== "near") { msg.textContent = "Give a latitude (-90 to 90), a longitude (-180 to 180) and a distance up to 5,000 km."; return; }
      } else next = { kind: v };
      save(next);
      btn.textContent = current.kind === "all" ? "Area" : "Area: " + (current.kind === "state" ? current.code.slice(3) : current.kind === "conus" ? "US 48" : current.km + " km");
      dlg.close();
    });
    if (current.kind !== "all") btn.textContent = "Area: " + (current.kind === "state" ? current.code.slice(3) : current.kind === "conus" ? "US 48" : current.km + " km");
    container.append(btn, dlg);
  }

  window.TicArea = { mountSettings: mountSettings, get: function () { return current; }, contains: contains,
    label: label, onChange: function (fn) { listeners.push(fn); }, _save: save };
})();
