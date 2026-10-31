/*! tic-time.js v1.3 · The Intelligence Company shared time display · canonical copy:
 *  D:\Projects\theintelligence-company\site\shared\tic-time.js (copy this file into each site; keep the version line).
 *
 *  House rule (Tom, 27 Oct 2026): store UTC; show times in the viewer's own time zone by default, always naming
 *  the zone; every site offers a settings menu for the time zone (automatic, Zulu/UTC, major zones, any IANA zone)
 *  and a 12- or 24-hour clock, saved in the browser. On *.theintelligence.company the choice is also kept in a
 *  cookie for the whole domain, so it follows the visitor from site to site.
 *
 *  Classic script: load it before your own code; it defines window.TicTime. No dependencies. Pair with tic-time.css.
 *    TicTime.format(isoOrDate, {date: true, seconds: false})  -> "27 Oct, 9:05 PM CDT" / "27 Oct 02:05Z"
 *      options: date (default true), time (default true), seconds, year, weekday (v1.1: "Mon 14:00 CDT"),
 *      zoneName: false (v1.1: leave the zone off, e.g. chart axes when the page names the zone once;
 *      TicTime.zoneLabel() gives that name, e.g. "CDT" or "Zulu (UTC)")
 *      year (v1.3): a full date in the house style, "31 Oct 2026", in the viewer's zone, Zulu included
 *    TicTime.onChange(fn)              re-render when the setting changes (also from another tab)
 *    TicTime.mountSettings(el)         adds a "Time" button that opens the settings dialog
 *    TicTime.renderAll(root)           fills every <time datetime="..." data-tic="datetime|time|date"> in root;
 *                                      add data-tic-year for the full date (v1.3)
 */
(function () {
  "use strict";
  var KEY = "tic-time-v1";
  var COOKIE = "tic_time";
  var ZONES = [
    ["UTC", "Zulu (UTC)"],
    ["America/New_York", "US Eastern"], ["America/Chicago", "US Central"], ["America/Denver", "US Mountain"],
    ["America/Phoenix", "Arizona"], ["America/Los_Angeles", "US Pacific"], ["America/Anchorage", "Alaska"],
    ["Pacific/Honolulu", "Hawaii"], ["Europe/London", "London"], ["Europe/Berlin", "Central Europe"],
    ["Europe/Kyiv", "Kyiv"], ["Europe/Moscow", "Moscow"], ["Asia/Jerusalem", "Israel"], ["Asia/Tehran", "Tehran"],
    ["Asia/Dubai", "Gulf (Dubai)"], ["Asia/Karachi", "Pakistan"], ["Asia/Kolkata", "India"],
    ["Asia/Shanghai", "China"], ["Asia/Taipei", "Taipei"], ["Asia/Seoul", "Korea"], ["Asia/Tokyo", "Japan"],
    ["Australia/Sydney", "Sydney"]
  ];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var listeners = [];

  function validZone(z) {
    if (typeof z !== "string" || !z) return false; // Intl accepts timeZone: undefined, so check first (v1.2)
    if (z === "auto" || z === "UTC") return true;
    try { new Intl.DateTimeFormat("en-US", { timeZone: z }); return true; } catch (e) { return false; }
  }
  function clean(s) {
    s = s || {};
    return { zone: validZone(s.zone) ? s.zone : "auto", clock: s.clock === "12" || s.clock === "24" ? s.clock : "auto" };
  }
  function sharedDomain() {
    var h = location.hostname;
    return /(^|\.)theintelligence\.company$/.test(h) ? "theintelligence.company" : null;
  }
  function readCookie() {
    var m = document.cookie.match(new RegExp("(?:^|; )" + COOKIE + "=([^;]*)"));
    if (!m) return null;
    var p = decodeURIComponent(m[1]).split("|");
    return { zone: p[0], clock: p[1] };
  }
  function load() {
    var s = null;
    try { s = readCookie(); } catch (e) { /* cookies blocked */ }
    if (!s) { try { s = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { /* storage blocked */ } }
    return clean(s);
  }
  var settings = load();

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch (e) { /* storage blocked */ }
    try {
      var d = sharedDomain();
      document.cookie = COOKIE + "=" + encodeURIComponent(settings.zone + "|" + settings.clock) +
        "; Path=/; Max-Age=31536000; SameSite=Lax" + (location.protocol === "https:" ? "; Secure" : "") +
        (d ? "; Domain=" + d : "");
    } catch (e) { /* cookies blocked */ }
  }
  function emit() { for (var i = 0; i < listeners.length; i++) { try { listeners[i](settings); } catch (e) { /* listener */ } } }

  function deviceZone() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch (e) { return "UTC"; }
  }
  function zone() { return settings.zone === "auto" ? deviceZone() : settings.zone; }
  function hour12() {
    if (settings.clock === "12") return true;
    if (settings.clock === "24") return false;
    if (zone() === "UTC") return false; // Zulu reads in 24-hour unless the viewer asks otherwise
    try { return new Intl.DateTimeFormat(undefined, { hour: "numeric" }).resolvedOptions().hour12 !== false; } catch (e) { return true; }
  }
  function toDate(v) {
    if (v instanceof Date) return v;
    if (typeof v === "number") return new Date(v);
    if (typeof v === "string") return new Date(v);
    return null;
  }

  function format(v, opts) {
    opts = opts || {};
    var d = toDate(v);
    if (!d || isNaN(d.getTime())) return "—";
    var z = zone(), h12 = hour12(), showDate = opts.date !== false, showTime = opts.time !== false;
    if (opts.year && showDate) {
      // v1.3: a full date reads the house way, "31 Oct 2026", whatever the zone or clock.
      var q;
      try {
        q = new Intl.DateTimeFormat("en-US", { timeZone: z, weekday: "short", day: "numeric", month: "numeric",
          year: "numeric" }).formatToParts(d);
      } catch (e) { return d.toISOString().slice(0, 10); }
      var pick = function (t) { var x = q.filter(function (r) { return r.type === t; })[0]; return x ? x.value : ""; };
      var full = (opts.weekday ? pick("weekday") + " " : "") + Number(pick("day")) + " " +
        MONTHS[Number(pick("month")) - 1] + " " + pick("year");
      if (!showTime) return full;
      return full + (z === "UTC" && !h12 ? " " : ", ") + format(d, { date: false, seconds: opts.seconds, zoneName: opts.zoneName });
    }
    if (z === "UTC" && !h12) {
      var p = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short",
        hour: "2-digit", minute: "2-digit", second: opts.seconds ? "2-digit" : undefined, hourCycle: "h23" }).formatToParts(d);
      var get = function (t) { var x = p.filter(function (q) { return q.type === t; })[0]; return x ? x.value : ""; };
      var t = get("hour") + ":" + get("minute") + (opts.seconds ? ":" + get("second") : "") + "Z";
      var day = get("day") + " " + get("month");
      var wd = opts.weekday ? get("weekday") + " " : "";
      return wd + (showDate && showTime ? day + " " + t : showTime ? t : day);
    }
    var o = { timeZone: z };
    if (opts.weekday) o.weekday = "short";
    if (showDate) { o.day = "numeric"; o.month = "short"; }
    if (showTime) {
      o.hour = "numeric"; o.minute = "2-digit"; if (opts.seconds) o.second = "2-digit";
      o.hourCycle = h12 ? "h12" : "h23"; if (opts.zoneName !== false) o.timeZoneName = "short";
    }
    try { return new Intl.DateTimeFormat(undefined, o).format(d); } catch (e) { return d.toISOString(); }
  }

  function zoneLabel() {
    if (zone() === "UTC") return "Zulu (UTC)";
    try {
      var p = new Intl.DateTimeFormat("en-US", { timeZone: zone(), timeZoneName: "short" }).formatToParts(new Date());
      var n = p.filter(function (q) { return q.type === "timeZoneName"; })[0];
      return n ? n.value : zone();
    } catch (e) { return zone(); }
  }

  function set(partial) {
    partial = Object.assign({}, partial);
    if (partial.zone !== undefined && !validZone(partial.zone)) delete partial.zone; // keep the current zone
    settings = clean(Object.assign({}, settings, partial));
    save();
    emit();
  }
  function onChange(fn) { listeners.push(fn); }
  window.addEventListener("storage", function (ev) { if (ev.key === KEY) { settings = load(); emit(); } });

  function renderAll(root) {
    var els = (root || document).querySelectorAll("time[datetime][data-tic]");
    for (var i = 0; i < els.length; i++) {
      var kind = els[i].getAttribute("data-tic");
      els[i].textContent = format(els[i].getAttribute("datetime"),
        { date: kind !== "time", time: kind !== "date", seconds: els[i].hasAttribute("data-tic-seconds"),
          year: els[i].hasAttribute("data-tic-year") });
    }
  }

  // ---- settings dialog (built with DOM calls only; no inline styles or HTML strings) ----
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) { if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) e.setAttribute(k, attrs[k] === true ? "" : attrs[k]); }
    (kids || []).forEach(function (c) { e.append(c instanceof Node ? c : document.createTextNode(String(c))); });
    return e;
  }
  function mountSettings(container, opts) {
    opts = opts || {};
    var btn = el("button", { type: "button", "class": "tic-time-btn", "aria-haspopup": "dialog", title: "Time zone and clock" },
      [opts.label || "Time"]);
    var dlg = el("dialog", { "class": "tic-time-dialog", "aria-label": "Time settings" });
    var zoneSel = el("select", { id: "tic-time-zone" });
    zoneSel.append(el("option", { value: "auto" }, ["Automatic (this device: " + deviceZone() + ")"]));
    ZONES.forEach(function (z) { zoneSel.append(el("option", { value: z[0] }, [z[1]])); });
    zoneSel.append(el("option", { value: "other" }, ["Other…"]));
    var other = el("input", { id: "tic-time-other", type: "text", placeholder: "IANA zone, e.g. Asia/Manila", spellcheck: "false", autocomplete: "off" });
    var otherRow = el("p", { "class": "tic-time-row tic-time-other" }, [el("label", { "for": "tic-time-other" }, ["Zone name "]), other]);
    var clockBox = el("fieldset", { "class": "tic-time-row" }, [el("legend", null, ["Clock"])]);
    [["auto", "Automatic"], ["12", "12-hour"], ["24", "24-hour"]].forEach(function (c) {
      var r = el("input", { type: "radio", name: "tic-time-clock", value: c[0], id: "tic-time-clock-" + c[0] });
      clockBox.append(el("label", { "for": r.id }, [r, " " + c[1]]));
    });
    var preview = el("p", { "class": "tic-time-preview", "aria-live": "polite" });
    var msg = el("p", { "class": "tic-time-msg", role: "alert" });
    var done = el("button", { type: "button", "class": "tic-time-done" }, ["Done"]);
    var reset = el("button", { type: "button", "class": "tic-time-reset" }, ["Use automatic"]);
    dlg.append(el("h2", null, ["Time settings"]),
      el("p", { "class": "tic-time-row" }, [el("label", { "for": "tic-time-zone" }, ["Time zone "]), zoneSel]),
      otherRow, clockBox, preview, msg, el("p", { "class": "tic-time-actions" }, [reset, done]),
      el("p", { "class": "tic-time-note" }, ["Saved in this browser. Data is stored in UTC."]));

    function sync() {
      var known = settings.zone === "auto" || ZONES.some(function (z) { return z[0] === settings.zone; });
      zoneSel.value = known ? settings.zone : "other";
      other.value = known ? "" : settings.zone;
      otherRow.hidden = known;
      var r = dlg.querySelector('input[name="tic-time-clock"][value="' + settings.clock + '"]');
      if (r) r.checked = true;
      preview.textContent = "Now: " + format(new Date(), { seconds: false });
      btn.textContent = (opts.label || "Time") + " · " + (zone() === "UTC" ? "Z" : format(new Date(), { date: false }).split(" ").pop());
    }
    zoneSel.addEventListener("change", function () {
      msg.textContent = "";
      if (zoneSel.value === "other") { otherRow.hidden = false; other.focus(); return; }
      set({ zone: zoneSel.value });
    });
    other.addEventListener("change", function () {
      var v = other.value.trim();
      if (validZone(v)) { msg.textContent = ""; set({ zone: v }); } else { msg.textContent = "Not a time zone name this browser knows."; }
    });
    clockBox.addEventListener("change", function (ev) { if (ev.target.name === "tic-time-clock") set({ clock: ev.target.value }); });
    reset.addEventListener("click", function () { msg.textContent = ""; set({ zone: "auto", clock: "auto" }); });
    done.addEventListener("click", function () { dlg.close(); });
    btn.addEventListener("click", function () { sync(); if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", ""); });
    onChange(sync);
    container.append(btn);
    document.body.append(dlg);
    sync();
    return btn;
  }

  window.TicTime = { version: "1.3", format: format, zone: zone, zoneLabel: zoneLabel, hour12: hour12, get: function () { return Object.assign({}, settings); },
    set: set, onChange: onChange, renderAll: renderAll, mountSettings: mountSettings, zones: ZONES.slice() };
})();
