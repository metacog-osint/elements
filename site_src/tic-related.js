/*! tic-related.js v1.0 · The Intelligence Company: "Elsewhere today", other layers' findings in the countries a
 *  page names, from COP's picture · canonical copy: the hub's site/shared/tic-related.js
 *  (copy into each site with tic-related.css; keep the version line).
 *
 *  From the suite design review (15 Nov 2026): each program page shows what the other layers report in the same
 *  places. It reads COP's agent index (data/agent/index.json, one row per item in COP's picture) once, when the card
 *  first comes near the screen, without cookies. The site's CSP connect-src must allow
 *  https://cop.theintelligence.company (the house bar's freshness dots need the same).
 *
 *  Use: an empty, hidden element where the card goes, then, once the page knows its countries,
 *    TicRelated.render(el, { countries: ["IR", "RU"], here: "blackout", names: { IR: "Iran" }, level: 3 })
 *  or declaratively, read when the script runs:
 *    <section class="card" data-tic-related data-countries="IR RU" data-here="blackout" hidden></section>
 *  Put the element in normal block flow (not straight inside a grid or flex row): while it waits, an empty marker
 *  span just before it is what is watched, and it is removed once the read starts.
 *  eager: true reads at once instead of waiting for the card to near the screen (tests; a hidden page never
 *  reports that). Calling render again with other countries redraws the card from the same read. The element stays hidden until
 *  the read succeeds, and a failed read leaves it hidden.
 *
 *  What it shows: items from the other programs (never the page's own), placed in one of those countries, current
 *  in COP's picture (not stale, not past valid_until) and from the last 48 hours (an item dated by day only: today
 *  or the two UTC days before, each of which still overlaps the last 48 hours, so a day posted the next morning
 *  shows; 15 Nov 2026. One dated by month only: never). Unusual readings first, then those in the countries the page
 *  lists first (list them strongest first), then the newest; three at most, one per program before any program
 *  repeats, then a link to COP for the rest. Items whose us_person_data is "individuals" are left out.
 *  Words: "Unusual" means unusual against that program's own baseline, never a warning; Vis's items are forecasts;
 *  a judgment says so; COP is never said to check or verify anything. No inline styles, no HTML strings.
 */
(function () {
  "use strict";
  var COP = "https://cop.theintelligence.company";
  var INDEX = COP + "/data/agent/index.json";
  var HOURS = 48, MAX = 3, OLD_PICTURE_H = 12;
  var LAYERS = { systems: "Systems", human: "Human", cyber: "Cyberspace", ems: "Spectrum", space: "Space", air: "Air",
    land: "Land and maritime" };
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var reading = null;

  function el(tag, cls, kids, attrs) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    for (var k in attrs || {}) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }

  function read() {
    if (!reading) {
      reading = fetch(INDEX, { credentials: "omit" }).then(function (r) {
        if (!r.ok) throw new Error("COP index " + r.status);
        return r.json();
      }).then(decode);
    }
    return reading;
  }

  // The index is columnar: `fields` names each column, and the repeated labels are numbers into `codes`.
  function decode(d) {
    if (!d || !Array.isArray(d.fields) || !Array.isArray(d.rows)) throw new Error("COP index: unexpected shape");
    var codes = d.codes || {};
    var rows = d.rows.map(function (r) {
      var o = {};
      d.fields.forEach(function (f, i) { o[f] = codes[f] && typeof r[i] === "number" ? codes[f][r[i]] : r[i]; });
      return o;
    });
    return { rows: rows, programs: d.programs || {}, at: d.bus_generated_at || d.generated_at || null };
  }

  function program(id, idx) {
    var list = (window.TicNav && window.TicNav.programs) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return { name: list[i].name, href: list[i].href, layer: list[i].layer };
    var p = idx.programs[id] || {};
    return { name: p.name || id, href: "https://" + id + ".theintelligence.company", layer: null };
  }

  function countryName(cc, names) {
    if (names && names[cc]) return names[cc];
    try { return new Intl.DisplayNames(["en"], { type: "region" }).of(cc) || cc; } catch (e) { return cc; }
  }

  function utcDay(ms) { var d = new Date(ms); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()); }

  function recent(r, now) {
    var t = Date.parse(r.data_as_of);
    if (isNaN(t) || r.data_as_of_precision === "month") return false;
    if (r.data_as_of_precision === "day") return utcDay(t) <= utcDay(now) && utcDay(t) >= utcDay(now) - 2 * 864e5;
    return t <= now + 36e5 && now - t <= HOURS * 36e5;
  }

  function pick(idx, opts, now) {
    var want = {};
    (opts.countries || []).forEach(function (c) { if (c) want[String(c).toUpperCase()] = true; });
    var here = opts.here || "";
    var hits = idx.rows.filter(function (r) {
      if (!r.program || r.program === here || r.stale || r.us_person_data === "individuals") return false;
      if (r.valid_until && Date.parse(r.valid_until) < now) return false;
      if (!(r.countries || []).some(function (c) { return want[c]; })) return false;
      return recent(r, now);
    });
    // The page lists its countries strongest first; an item ranks by its best-placed country.
    var order = {};
    (opts.countries || []).forEach(function (c, i) { c = String(c).toUpperCase(); if (!(c in order)) order[c] = i; });
    var rank = function (r) { return Math.min.apply(null, (r.countries || []).map(function (c) { return c in order ? order[c] : 1e9; })); };
    hits.sort(function (a, b) {
      var ua = a.tier === "routine" ? 1 : 0, ub = b.tier === "routine" ? 1 : 0;
      return ua - ub || rank(a) - rank(b) || Date.parse(b.data_as_of) - Date.parse(a.data_as_of);
    });
    return hits;
  }

  // The first `n` with one item per program, then the rest in order if there are fewer programs than places.
  function spread(hits, n) {
    var out = [], seen = {};
    hits.forEach(function (r) { if (out.length < n && !seen[r.program]) { seen[r.program] = true; out.push(r); } });
    hits.forEach(function (r) { if (out.length < n && out.indexOf(r) < 0) out.push(r); });
    return out;
  }

  function when(r) {
    if (r.data_as_of_precision === "day") {
      var d = new Date(r.data_as_of);  // a date from the source: give the date, never a time or another zone
      return el("span", "tic-rel-when", [d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear()]);
    }
    var t = el("time", "tic-rel-when", [r.data_as_of.replace("T", " ").slice(0, 16) + " UTC"],
      { datetime: r.data_as_of, "data-tic": "datetime" });
    return t;
  }

  function tag(r, p) {
    if (r.kind === "forecast") return "Forecast";
    if (r.status_class === "assessed" && r.tier === "warning") return p.name + "'s judgment";
    if (r.tier === "anomaly") return "Unusual";
    if (r.status_class === "claimed") return "As claimed";
    return null;
  }

  function ago(iso, now) {
    var h = (now - Date.parse(iso)) / 36e5;
    if (isNaN(h)) return null;
    if (h < 1) return Math.max(1, Math.round(h * 60)) + " min ago";
    if (h < 48) return Math.round(h) + " h ago";
    return Math.round(h / 24) + " days ago";
  }

  function draw(target, idx, opts) {
    var now = Date.now();
    var hits = pick(idx, opts, now);
    var level = Math.min(6, Math.max(2, Number(opts.level) || 3));
    var ccs = (opts.countries || []).map(function (c) { return String(c).toUpperCase(); });
    var where = ccs.length === 1 ? countryName(ccs[0], opts.names) : "the countries on this page";
    var kids = [
      el("h" + level, "tic-rel-h", ["Elsewhere today"], { id: (target.id || "tic-related") + "-h" }),
      el("p", "tic-rel-sub", ["What the other programs report in " + where + " from the last 48 hours, as COP's picture holds them."])
    ];
    var unusual = false;
    if (!hits.length) {
      kids.push(el("p", "tic-rel-empty", ["No other program reports anything there in the last 48 hours."]));
    } else {
      var ul = el("ul", "tic-rel-list");
      spread(hits, MAX).forEach(function (r) {
        var p = program(r.program, idx);
        var t = tag(r, p);
        if (t === "Unusual") unusual = true;
        var places = (r.countries || []).filter(function (c) { return ccs.indexOf(c) >= 0; })
          .map(function (c) { return countryName(c, opts.names); });
        var href = r.link && p.href && r.link.indexOf(p.href) === 0 ? r.link : p.href;
        var meta = [when(r), " · ", places.join(", ")];
        if (t) meta.push(" · ", el("span", "tic-rel-tag", [t]));
        ul.appendChild(el("li", "tic-rel-item" + (p.layer ? " tic-rel-l-" + p.layer : ""), [
          el("p", "tic-rel-who", [el("span", "tic-rel-dot", [], { "aria-hidden": "true" }), el("strong", "", [p.name]),
            p.layer && LAYERS[p.layer] ? el("span", "tic-rel-layer", [" · " + LAYERS[p.layer]]) : null]),
          el("p", "tic-rel-t", [r.title || "(no title)"]),
          el("p", "tic-rel-meta", meta),
          el("a", "tic-rel-open", ["Open in " + p.name + " ↗", el("span", "tic-rel-sr", [" (opens in a new tab)"])],
            { href: href, target: "_blank", rel: "noopener" })
        ]));
      });
      kids.push(ul);
    }
    var foot = [];
    if (hits.length > MAX) foot.push(hits.length - MAX + " more on COP. ");
    var age = idx.at ? ago(idx.at, now) : null;
    if (age) foot.push("COP's picture was built " + age + ". ");
    if (idx.at && now - Date.parse(idx.at) > OLD_PICTURE_H * 36e5) foot.push("That is older than usual. ");
    if (unusual) foot.push("Unusual means unusual against that program's own baseline; it is not a warning. ");
    foot.push("Each finding is its program's own: open it there for sources and method. ");
    foot.push(el("a", "tic-rel-cop", ["See them on COP →"], { href: COP + "/" }));
    kids.push(el("p", "tic-rel-foot", foot));
    target.classList.add("tic-rel");
    if (!target.hasAttribute("aria-labelledby")) target.setAttribute("aria-labelledby", (target.id || "tic-related") + "-h");
    target.replaceChildren.apply(target, kids);
    if (window.TicTime) window.TicTime.renderAll(target);
    target.hidden = false;
  }

  function whenNear(target, fn) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    if (target._ticNear) target._ticNear();
    // A hidden element has no box and never intersects, and its parent may be on screen long before the card is
    // (Blackout's Overview is), so watch an empty marker just before it, which has no height in block flow.
    var mark = null, watch = target;
    if (target.hidden && target.parentNode) {
      mark = document.createElement("span");
      mark.className = "tic-rel-near";
      mark.setAttribute("aria-hidden", "true");
      target.parentNode.insertBefore(mark, target);
      watch = mark;
    }
    var io;
    var stop = function () {
      io.disconnect();
      if (mark && mark.parentNode) mark.parentNode.removeChild(mark);
      target._ticNear = null;
    };
    io = new IntersectionObserver(function (es) {
      if (es.some(function (e) { return e.isIntersecting; })) { stop(); fn(); }
    }, { rootMargin: "400px 0px" });
    target._ticNear = stop;
    io.observe(watch);
  }

  function render(target, opts) {
    if (!target) return Promise.resolve(false);
    opts = opts || {};
    target._ticRelated = opts;
    return new Promise(function (resolve) {
      var go = function () {
        read().then(function (idx) {
          if (target._ticRelated === opts) draw(target, idx, opts);
          resolve(true);
        }, function () { resolve(false); });
      };
      if (reading || opts.eager) go(); else whenNear(target, go);
    });
  }

  var tracked = false;
  function retime() {
    if (tracked || !window.TicTime || !window.TicTime.onChange) return;
    tracked = true;
    window.TicTime.onChange(function () {
      var els = document.querySelectorAll(".tic-rel");
      for (var i = 0; i < els.length; i++) window.TicTime.renderAll(els[i]);
    });
  }

  function auto() {
    retime();
    var els = document.querySelectorAll("[data-tic-related]");
    for (var i = 0; i < els.length; i++) {
      var cc = (els[i].getAttribute("data-countries") || "").split(/[\s,]+/).filter(Boolean);
      if (cc.length) render(els[i], { countries: cc, here: els[i].getAttribute("data-here") || "",
        level: els[i].getAttribute("data-level") });
    }
  }

  window.TicRelated = { version: "1.0", render: function (t, o) { retime(); return render(t, o); }, _pick: pick, _decode: decode };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", auto); else auto();
})();
