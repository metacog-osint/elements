/*! tic-nav.js v2.1 · The Intelligence Company house bar: a link home and a Programs menu · canonical copy:
 *  the hub's site/shared/tic-nav.js (copy into each site with tic-nav.css; keep the version line).
 *  SPDX-License-Identifier: MIT. Copyright (c) 2026 The Intelligence Company. MIT in every repository it is
 *  copied into, whatever that repository's own licence.
 *
 *  1 Nov 2026: every program site needs a link back to the home page, and a dropdown of all programs, each
 *  labelled with its primary layer or topic, with a fuller description on mouse-over.
 *
 *  Classic script, no dependencies, CSP-safe (DOM calls only: no inline styles, no HTML strings). Load it at the end
 *  of <body> or with `defer`. It puts the bar first in <body>, or inside <div id="tic-nav"></div> if the page has one
 *  (use that when a fixed header would cover the bar). The current program is found from the host name, or from
 *  <script src="tic-nav.js" data-current="vigil">, and is marked "You are here". Program links open in the same tab:
 *  this is site navigation. Keep PROGRAMS in step with the hub's oe/oe.js and product list.
 *    TicNav.mount(el?)   mounts the bar (done automatically once)
 *    TicNav.programs     the list below
 *  On the hub itself (v1.11, 14 Nov 2026: the Programs menu on theintelligence.company too), load it with
 *  data-home="here": the home link becomes plain text, since the reader is already home.
 *
 *  v1.12 (14 Nov 2026: "each page's header should freeze as the page scrolls down… If the user chooses to
 *  minimize the header bar, we should have a button for that, too, on the header"): the bar is fixed to the top of
 *  the window, with an empty spacer after it holding its place in the page, so it stays put whether it is first in
 *  <body> or inside #tic-nav. A button at its right end minimizes it to a small tab (the Programs button and a
 *  button to bring the bar back); the choice is kept like the time settings, in a cookie for the whole
 *  theintelligence.company domain (else localStorage), so it follows the visitor from site to site.
 *  While mounted, <html> has the class tic-house-on (and tic-house-minimized when minimized), and tic-nav.css sets
 *  --tic-house-h on it: 34px for the full bar, 0px minimized. A site whose own header is sticky or fixed at the top
 *  uses `top: var(--tic-house-h, 0px)` to sit below the bar.
 *    TicNav.minimized()      true when the bar is minimized
 *    TicNav.minimize(bool)   minimizes (true) or restores (false) it, and remembers the choice
 *  v1.13 (15 Nov 2026): Wake (shipping through maritime chokepoints, beta) in the Programs menu.
 *
 *  v2.1 (15 Nov 2026): Relief (humanitarian appeals and disease outbreaks, live) in the Programs menu, Human layer.
 *
 *  v2.0 (15 Nov 2026, from the suite design review): the menu groups programs by their home layer, in the hub
 *  drawing's order (COP first as every layer, then Systems down to Land and maritime, then other tools); each item
 *  shows its topic under its layer's heading. COP's text says what COP is: every layer on one map, so places where
 *  more than one layer reports stand out (15 Nov 2026). The panel ends with "See it on COP", which opens COP
 *  with every layer showing (not filtered to one family: the point is seeing the program beside the others).
 *  Freshness dots: when the menu first opens, the bar reads COP's health check and marks each program on time,
 *  running late or without current data, in words as well as colour. That needs COP's origin in the page's
 *  connect-src, so a site turns it on with data-health="on" once its CSP allows https://cop.theintelligence.company.
 *  COP itself (same origin) and the hub (which already fetches it, window.ticCopHealth) get it without the attribute;
 *  data-health="off" turns it off. One request, only when the menu opens, with no cookies; a failure leaves no dots.
 */
(function () {
  "use strict";
  var HOME = "https://theintelligence.company/";
  var ALL = "https://theintelligence.company/#layers";
  var COP = "https://cop.theintelligence.company";
  var COP_HEALTH = COP + "/data/health.json";
  var script = document.currentScript;

  // label: primary layer of the operational environment, then the topic. layer: the home layer on the hub's drawing
  // ("all" for COP; none for the other tools). group: across the layers, or other tools.
  var PROGRAMS = [
    { id: "cop", name: "COP", href: COP, status: "beta", group: "layers", layer: "all",
      label: "Every layer · common operational picture",
      short: "Every layer's findings on one map, so places where more than one layer reports stand out.",
      long: "The common operational picture: every layer's findings on one map, so a place or topic that turns up in more than one layer stands out. Outages are already read against hazards, notices and press attention in the same country; convergence scoring, checked by Verdict, is in development." },
    { id: "watchfloor", name: "Watchfloor", href: "https://watchfloor.theintelligence.company", status: "beta", group: "layers", layer: "systems",
      label: "Systems · conflict warning",
      short: "A daily warning picture for each watched conflict zone and topic.",
      long: "A daily warning picture for the conflict zones and strategic topics on its watch list, built from the world's news against each zone's own usual level, and split by source group." },
    { id: "headwind", name: "Headwind", href: "https://headwind.theintelligence.company", status: "beta", group: "layers", layer: "systems",
      label: "Systems · economic stress",
      short: "Currencies, energy and food prices against their own normal range, and sanctions-list changes.",
      long: "Economic stress as measurements. Currencies, energy prices and food prices are each compared with their own past changes and marked unusual only when far outside them. Changes to the OFAC and UN Security Council sanctions lists and twelve US screening lists are given as counts, with sanctioned vessels named. Also new BIS and OFAC rules from the Federal Register, US import reliance for minerals, and a calendar of coming decisions. Not forecasts and not investment advice." },
    { id: "context", name: "Context", href: "https://context.theintelligence.company", status: "live", group: "layers", layer: "human",
      label: "Human · press framing",
      short: "How the world's press covers each watched zone and topic.",
      long: "How the world's press covers each watched conflict zone and strategic topic: attention, escalation and framing, refreshed twice a day from GDELT." },
    { id: "undertow", name: "Undertow", href: "https://undertow.theintelligence.company", status: "beta", group: "layers", layer: "human",
      label: "Human · influence operations",
      short: "Covert influence operations that platforms and governments have taken down, at the level of the operation.",
      long: "Covert influence operations as the platforms and governments that disrupted them report them: Meta's takedown networks, Google's influence-operations bulletins, OpenAI's threat reports, TikTok's reports under the EU Code of Conduct, and the EEAS's named operations. Each gives the origin the publisher assessed, the targets, and the DISARM techniques described, with a STIX 2.1 export. Operations only: no account handles, links or names of individuals." },
    { id: "relief", name: "Relief", href: "https://relief.theintelligence.company", status: "beta", group: "layers", layer: "human",
      label: "Human · humanitarian response",
      short: "Where the Red Cross and Red Crescent are asking for help, and where WHO is reporting outbreaks.",
      long: "Where the Red Cross and Red Crescent are asking for help, and where WHO is reporting outbreaks: IFRC GO appeals and WHO Disease Outbreak News, as they publish them. Measurements only. Updated every six hours." },
    { id: "vigil", name: "Vigil", href: "https://vigil.theintelligence.company", status: "live", group: "layers", layer: "cyber",
      label: "Cyberspace · threat intelligence",
      short: "Ransomware, exploited vulnerabilities and threat indicators.",
      long: "Cyber threat intelligence that records why it believes things: ransomware groups and their leak-site claims, exploited vulnerabilities and advisories, and threat indicators, with the history and every judgment call kept." },
    { id: "blackout", name: "Blackout", href: "https://blackout.theintelligence.company", status: "beta", group: "layers", layer: "cyber",
      label: "Cyberspace · internet and power outages",
      short: "Where the lights go out and the internet goes dark, worldwide.",
      long: "Where the lights go out and the internet goes dark: country outages from Georgia Tech IODA and Cloudflare Radar, censorship measurements from OONI, BGP hijacks and route leaks from Cloudflare Radar, the Zaporizhzhya nuclear plant's off-site power as the IAEA reports it, US power outages by county and US grid operators' demand against their own forecasts, a watch on the Starlink, Amazon, Microsoft and Google networks and on eleven providers' own status pages, and a hand-compiled register of submarine cable corridors. A drop is called a likely shutdown only when OONI shows blocking in the same country. Updated every four hours." },
    { id: "noisefloor", name: "Noisefloor", href: "https://noisefloor.theintelligence.company", status: "live", group: "layers", layer: "ems",
      label: "Spectrum · GPS interference",
      short: "Where GPS is being jammed or spoofed, mapped every day.",
      long: "Where GPS and other satellite navigation is jammed or spoofed, mapped every day from aircraft and ship position reports, with satellite and space-weather context." },
    { id: "orbit", name: "Orbit", href: "https://orbit.theintelligence.company", status: "beta", group: "layers", layer: "space",
      label: "Space · orbital activity",
      short: "What changed in Earth orbit: launches, scheduled launches, reentries and satellite catalog changes.",
      long: "What changed in Earth orbit, from public catalogs: orbital launches of the last 7 and 30 days, launches scheduled for the next 14 days, reentries, and changes to the satellite catalog between Orbit's own readings, with objects in orbit counted by owner. From Jonathan McDowell's GCAT (CC BY 4.0) and The Space Devs' Launch Library 2. Measurements and reports only; Orbit adds no judgment. Updated every six hours." },
    { id: "launch", name: "Launch", href: "https://launch.theintelligence.company", status: "beta", group: "layers", layer: "space",
      label: "Space · launch closures",
      short: "Launch and reentry closure areas: what is announced now, which scheduled launches coincide, and each pad's history.",
      long: "Launch and reentry closure areas from official notices: the FAA's space-operations flight restrictions in force, scheduled launches that coincide with an announced closure area in time, in time and place, or as a launch since dated, a searchable history of closures since 2023 with each notice's own text, and where each pad's closures fall. Worldwide NOTAMs wait on FAA access." },
    { id: "cordon", name: "Cordon", href: "https://cordon.theintelligence.company", status: "beta", group: "layers", layer: "air",
      label: "Air · hazard notices",
      short: "Where authorities warn people away.",
      long: "Where authorities warn people away: State Department travel advisories and embassy departure status, EASA conflict-zone bulletins for airspace, and NGA navigational warnings at sea." },
    { id: "vis", name: "Vis", href: "https://vis.theintelligence.company", status: "beta", group: "layers", layer: "air",
      label: "Air · operational weather",
      short: "Operational weather and night light for each watched conflict zone.",
      long: "Operational weather and illumination for Watchfloor's conflict zones: how likely wind, poor visibility, heavy rain or snow, icing, extreme heat or cold, or low cloud are to reach indicative limits at named airfields and ports over the next 7 days, from the NOAA and ECMWF ensembles, with each night's moonlight and darkness. Updated twice a day; not an official forecast." },
    { id: "elements", name: "Elements", href: "https://elements.theintelligence.company", status: "beta", group: "layers", layer: "land",
      label: "Land and maritime · natural hazards",
      short: "Natural hazards as the authorities report them.",
      long: "Natural hazards as the authorities report them, on one map. Worldwide: earthquakes from USGS (with impact alerts) and EMSC, satellite fire detections, GDACS multi-hazard alerts and Copernicus disaster mapping. Regional: weather warnings for the US and Europe, hurricane-center storms, and tsunami messages for North America, the Pacific and the Caribbean. US only for now: wildfire incidents, severe-storm outlooks, drought and volcano alert levels. Weather for more of the world is planned." },
    { id: "wake", name: "Wake", href: "https://wake.theintelligence.company", status: "beta", group: "layers", layer: "land",
      label: "Land and maritime · shipping chokepoints",
      short: "Ships crossing the world's maritime chokepoints, week by week, against their own normal.",
      long: "Vessel transits through 28 maritime chokepoints, from Hormuz and Bab el-Mandeb to Malacca and Panama: IMF PortWatch's daily counts by ship type, as weekly means compared with the 90 days before and the same weeks a year earlier. Updated by hand once a week. Measurements only." },
    { id: "propertycast", name: "PropertyCast", href: "https://propertycast.theintelligence.company", status: "live", group: "tools",
      label: "Weather · one property",
      short: "A hyperlocal forecast that checks itself every hour.",
      long: "A hyperlocal forecast for one property that verifies itself every hour against its own weather station, with a garden decision layer." },
    { id: "activation", name: "Title 10 Field Guide", href: "https://activation.theintelligence.company", status: "live", group: "tools",
      label: "Guard members on federal orders",
      short: "Pay, benefits and steps for activated Air Guard members.",
      long: "What activated Air Guard members earn on federal orders, what gets missed, and what to do before and after release. Unofficial; compiled from public sources." },
    { id: "listeningpost", name: "Listening Post", href: "https://listeningpost.theintelligence.company", status: "invite", group: "tools",
      label: "Job search",
      short: "A job-search workspace, by invitation.",
      long: "A job-search workspace: each opening scored against your own criteria, new postings found by a weekly sweep, and drafts you review and send yourself. Google sign-in, by invitation." }
  ];
  var STATUS = { live: "Live", beta: "Beta", invite: "Invite only" };
  // v2.0: one heading per layer, in the hub drawing's order (oe/oe.js LAYERS), then the tools outside the drawing.
  var GROUPS = [["all", "Every layer"], ["systems", "Systems"], ["human", "Human"], ["cyber", "Cyberspace"],
    ["ems", "Spectrum"], ["space", "Space"], ["air", "Air"], ["land", "Land and maritime"], ["tools", "Other tools"]];
  // COP's health states, in words (COP's own legend calls a stale program "no current data").
  var FRESH = { fresh: "On time", late: "Running late", stale: "No current data" };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function hostOf(u) { try { return new URL(u).hostname; } catch (e) { return ""; } }
  function currentId() {
    var d = script && script.getAttribute("data-current");
    if (d) return d;
    var h = location.hostname;
    for (var i = 0; i < PROGRAMS.length; i++) if (hostOf(PROGRAMS[i].href) === h) return PROGRAMS[i].id;
    return "";
  }
  function groupOf(p) { return p.group === "tools" ? "tools" : p.layer; }
  // Under a layer's heading the layer's name would repeat, so the item shows only the topic.
  function topicOf(p) {
    if (p.group === "tools") return p.label;
    var i = p.label.indexOf(" · ");
    var t = i < 0 ? p.label : p.label.slice(i + 3);
    return t.charAt(0).toUpperCase() + t.slice(1);
  }
  function ago(iso) {
    var t = Date.parse(iso);
    if (!(t > 0)) return "";
    var m = Math.max(0, Math.round((Date.now() - t) / 60000));
    if (m < 60) return m + " min ago";
    var h = Math.round(m / 60);
    return h < 48 ? h + " h ago" : Math.round(h / 24) + " days ago";
  }

  // v1.12: minimized or not, kept the way tic-time.js keeps its settings. Written only when the visitor presses the
  // button, so a visitor who never does gets no cookie and no storage.
  var KEY = "tic-nav-v1", COOKIE = "tic_nav";
  function sharedDomain() {
    return /(^|\.)theintelligence\.company$/.test(location.hostname) ? "theintelligence.company" : null;
  }
  function loadMini() {
    var v = null;
    try {
      var m = document.cookie.match(new RegExp("(?:^|; )" + COOKIE + "=([^;]*)"));
      if (m) v = decodeURIComponent(m[1]);
    } catch (e) { /* cookies blocked */ }
    if (!v) { try { v = localStorage.getItem(KEY); } catch (e) { /* storage blocked */ } }
    return v === "min";
  }
  function saveMini(min) {
    var v = min ? "min" : "full";
    try { localStorage.setItem(KEY, v); } catch (e) { /* storage blocked */ }
    try {
      var d = sharedDomain();
      document.cookie = COOKIE + "=" + v + "; Path=/; Max-Age=31536000; SameSite=Lax" +
        (location.protocol === "https:" ? "; Secure" : "") + (d ? "; Domain=" + d : "");
    } catch (e) { /* cookies blocked */ }
  }

  // v2.0: COP's health check, read once, only when the menu first opens.
  function healthWanted() {
    var a = script && script.getAttribute("data-health");
    if (a === "off") return false;
    return a === "on" || location.origin === COP || !!window.ticCopHealth;
  }
  var health = null;
  function loadHealth() {
    if (!health) {
      health = Promise.resolve(window.ticCopHealth || (window.fetch ? fetch(COP_HEALTH, { credentials: "omit" })
        .then(function (r) { return r.ok ? r.json() : null; }) : null))
        .then(function (h) { return h && h.programs ? h : null; }, function () { return null; });
    }
    return health;
  }

  var mounted = false, setMini = null;
  function mount(target) {
    if (mounted) return;
    mounted = true;
    var here = currentId();
    var nav = el("nav", "tic-house");
    nav.setAttribute("aria-label", "The Intelligence Company");
    var inner = el("div", "tic-house-in");
    var atHome = script && script.getAttribute("data-home") === "here";
    var home;
    if (atHome) {
      home = el("span", "tic-house-home", "The Intelligence Company");
    } else {
      home = el("a", "tic-house-home");
      home.href = HOME;
      home.append(el("span", "tic-house-arrow", "←"), " The Intelligence Company");
      home.firstChild.setAttribute("aria-hidden", "true");
    }

    var menu = el("div", "tic-house-menu");
    var btn = el("button", "tic-house-btn");
    btn.type = "button";
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-controls", "tic-house-panel");
    btn.append("Programs ", el("span", "tic-house-caret", "▾"));
    btn.lastChild.setAttribute("aria-hidden", "true");

    var panel = el("div", "tic-house-panel");
    panel.id = "tic-house-panel";
    panel.hidden = true;
    var cols = el("div", "tic-house-cols");
    var list = el("div", "tic-house-list");
    var detail = el("div", "tic-house-detail");
    detail.setAttribute("aria-hidden", "true"); // visual only; screen readers get each link's description
    var dName = el("p", "tic-house-dname"), dMeta = el("p", "tic-house-dmeta"), dLong = el("p", "tic-house-dlong");
    detail.append(dName, dMeta, dLong);

    var items = [], shown = null, fresh = {};
    function meta(p) {
      return p.label + " · " + STATUS[p.status] + (fresh[p.id] ? " · " + FRESH[fresh[p.id]].toLowerCase() : "") +
        (p.id === here ? " · you are here" : "");
    }
    function show(p, a) {
      shown = a;
      dName.textContent = p.name;
      dMeta.textContent = meta(p);
      dLong.textContent = p.long;
      items.forEach(function (x) { x.classList.toggle("on", x === a); });
    }
    GROUPS.forEach(function (g) {
      var ps = PROGRAMS.filter(function (p) { return groupOf(p) === g[0]; });
      if (!ps.length) return;
      var box = el("div", "tic-house-g");
      box.append(el("p", "tic-house-group", g[1]));
      var ul = el("ul", "tic-house-ul");
      ps.forEach(function (p) {
        var li = el("li");
        var a = el("a", "tic-house-item");
        a.href = p.href;
        var nameRow = el("span", "tic-house-name", p.name);
        if (p.id === here) {
          a.setAttribute("aria-current", "page");
          a.classList.add("here");
          nameRow.append(el("span", "tic-house-here", "You are here"));
        }
        var st = el("span", "tic-house-st st-" + p.status);
        st.append(el("span", "tic-house-stw", STATUS[p.status]));
        var label = el("span", "tic-house-label", topicOf(p));
        a.append(nameRow, st, label, el("span", "tic-house-short", p.short));
        var desc = el("span", "tic-house-sr", p.long);
        desc.id = "tic-house-d-" + p.id;
        a.setAttribute("aria-describedby", desc.id);
        a.addEventListener("mouseenter", function () { show(p, a); });
        a.addEventListener("focus", function () { show(p, a); });
        li.append(a, desc);
        ul.append(li);
        items.push(a);
        a._p = p;
        a._st = st;
        a._label = label;
      });
      box.append(ul);
      list.append(box);
    });
    cols.append(list, detail);
    var foot = el("div", "tic-house-foot");
    var all = el("a", "tic-house-all", "How the programs fit together, and what's planned →");
    all.href = ALL;
    foot.append(all);
    // v2.0: "See it on COP", with every layer showing. Not on COP itself.
    var hereP = PROGRAMS.filter(function (p) { return p.id === here; })[0];
    var copLink = null;
    if (here !== "cop") {
      copLink = el("a", "tic-house-cop",
        hereP && hereP.group === "layers" ? "See " + hereP.name + " with the other layers on COP →" : "See every layer together on COP →");
      copLink.href = COP;
      foot.append(copLink);
    }
    var note = el("p", "tic-house-fnote");
    note.hidden = true;
    panel.append(cols, foot, note);
    menu.append(btn, panel);

    function applyHealth(h) {
      if (!h) return;
      var state = {};
      h.programs.forEach(function (x) { if (x && x.id) state[x.id] = x.state; });
      items.forEach(function (a) {
        var p = a._p, s = state[p.id];
        if (!FRESH[s]) return;
        fresh[p.id] = s;
        var dot = el("span", "tic-house-dot f-" + s);
        dot.title = FRESH[s] + ", in COP's health check";
        dot.append(el("span", "tic-house-sr", FRESH[s] + "."));
        a._st.insertBefore(dot, a._st.firstChild);
        if (s !== "fresh") a._label.append(el("span", "tic-house-fw f-" + s, " · " + FRESH[s].toLowerCase()));
      });
      var when = ago(h.generated_at);
      note.textContent = "Dots: on time, running late or no current data, as COP's health check found" + (when ? " " + when : "") + ".";
      note.hidden = false;
      if (shown) show(shown._p, shown);
    }

    // v1.12: the minimize button, at the bar's right end. Minimized, the bar shrinks to a tab holding the Programs
    // button and this button, which brings the bar back. The same button stays focused either way.
    var tools = el("div", "tic-house-tools");
    var mini = el("button", "tic-house-toggle");
    mini.type = "button";
    mini.append(el("span", "tic-house-chev"), el("span", "tic-house-sr"));
    mini.firstChild.setAttribute("aria-hidden", "true");
    tools.append(menu, mini);
    inner.append(home, tools);
    nav.append(inner);
    // Holds the bar's place in the page, since the bar itself is fixed to the top of the window.
    var room = el("div", "tic-house-room");
    room.setAttribute("aria-hidden", "true");

    var root = document.documentElement;
    setMini = function (min, remember) {
      nav.classList.toggle("is-mini", min);
      root.classList.toggle("tic-house-minimized", min);
      var word = min ? "Show the house bar" : "Minimize the house bar";
      mini.lastChild.textContent = word;
      mini.title = word;
      if (remember) saveMini(min);
    };
    setMini(loadMini(), false);
    mini.addEventListener("click", function () { setMini(!nav.classList.contains("is-mini"), true); });

    var asked = false;
    function open() {
      panel.hidden = false;
      btn.setAttribute("aria-expanded", "true");
      var start = items.filter(function (a) { return a._p.id === here; })[0] || items[0];
      show(start._p, start);
      if (!asked && healthWanted()) { asked = true; loadHealth().then(applyHealth); }
    }
    function close(focusBtn) {
      if (panel.hidden) return;
      panel.hidden = true;
      btn.setAttribute("aria-expanded", "false");
      if (focusBtn) btn.focus();
    }
    btn.addEventListener("click", function () { if (panel.hidden) open(); else close(false); });
    document.addEventListener("click", function (ev) { if (!menu.contains(ev.target)) close(false); });
    menu.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); close(true); return; }
      if (panel.hidden || ["ArrowDown", "ArrowUp", "Home", "End"].indexOf(ev.key) < 0) return;
      ev.preventDefault();
      var i = items.indexOf(document.activeElement);
      var n = ev.key === "Home" ? 0 : ev.key === "End" ? items.length - 1
        : ev.key === "ArrowDown" ? (i + 1) % items.length : (i <= 0 ? items.length - 1 : i - 1);
      items[n].focus();
    });
    menu.addEventListener("focusout", function () {
      setTimeout(function () { if (!menu.contains(document.activeElement)) close(false); }, 0);
    });

    var slot = target || document.getElementById("tic-nav");
    if (slot) slot.append(nav, room);
    else { document.body.insertBefore(room, document.body.firstChild); document.body.insertBefore(nav, room); }
    root.classList.add("tic-house-on");
  }

  window.TicNav = {
    version: "2.1", programs: PROGRAMS.slice(), mount: mount,
    minimized: function () { return document.documentElement.classList.contains("tic-house-minimized"); },
    minimize: function (min) { if (setMini) setMini(min !== false, true); }
  };
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", function () { mount(); });
})();
