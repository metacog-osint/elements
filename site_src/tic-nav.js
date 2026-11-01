/*! tic-nav.js v1.1 · The Intelligence Company house bar: a link home and a Programs menu · canonical copy:
 *  D:\Projects\theintelligence-company\site\shared\tic-nav.js (copy into each site with tic-nav.css; keep the version line).
 *
 *  Tom, 1 Nov 2026: every program site needs a link back to the home page, and a dropdown of all programs, each
 *  labelled with its primary layer or topic, with a fuller description on mouse-over.
 *
 *  Classic script, no dependencies, CSP-safe (DOM calls only: no inline styles, no HTML strings). Load it at the end
 *  of <body> or with `defer`. It puts the bar first in <body>, or inside <div id="tic-nav"></div> if the page has one
 *  (use that when a fixed header would cover the bar). The current program is found from the host name, or from
 *  <script src="tic-nav.js" data-current="vigil">, and is marked "You are here". Program links open in the same tab:
 *  this is site navigation. Keep PROGRAMS in step with the hub's oe/oe.js and product list.
 *    TicNav.mount(el?)   mounts the bar (done automatically once)
 *    TicNav.programs     the list below
 */
(function () {
  "use strict";
  var HOME = "https://theintelligence.company/";
  var ALL = "https://theintelligence.company/#layers";
  var script = document.currentScript;

  // label: primary layer of the operational environment, then the topic; group: across the layers, or other tools.
  var PROGRAMS = [
    { id: "cop", name: "COP", href: "https://cop.theintelligence.company", status: "beta", group: "layers",
      label: "Every layer · common operational picture",
      short: "Every program's latest findings on one map.",
      long: "The common operational picture: every program's latest findings on one map, with today's top five, what else is unusual, and each feed's health." },
    { id: "watchfloor", name: "Watchfloor", href: "https://watchfloor.theintelligence.company", status: "beta", group: "layers",
      label: "Systems · conflict warning",
      short: "A daily warning picture for each watched conflict zone and topic.",
      long: "A daily warning picture for the conflict zones and strategic topics on its watch list, built from the world's news against each zone's own usual level, and split by source group." },
    { id: "context", name: "Context", href: "https://context.theintelligence.company", status: "live", group: "layers",
      label: "Human · press framing",
      short: "How the world's press covers each watched zone and topic.",
      long: "How the world's press covers each watched conflict zone and strategic topic: attention, escalation and framing, refreshed twice a day from GDELT." },
    { id: "vigil", name: "Vigil", href: "https://vigil.theintelligence.company", status: "live", group: "layers",
      label: "Cyberspace · threat intelligence",
      short: "Ransomware, exploited vulnerabilities and threat indicators.",
      long: "Cyber threat intelligence that records why it believes things: ransomware groups and their leak-site claims, exploited vulnerabilities and advisories, and threat indicators, with the history and every judgment call kept." },
    { id: "noisefloor", name: "Noisefloor", href: "https://noisefloor.theintelligence.company", status: "live", group: "layers",
      label: "Spectrum · GPS interference",
      short: "Where GPS is being jammed or spoofed, mapped every day.",
      long: "Where GPS and other satellite navigation is jammed or spoofed, mapped every day from aircraft and ship position reports, with satellite and space-weather context." },
    { id: "cordon", name: "Cordon", href: "https://cordon.theintelligence.company", status: "beta", group: "layers",
      label: "Air · hazard notices",
      short: "Where authorities warn people away.",
      long: "Where authorities warn people away: State Department travel advisories and embassy departure status, EASA conflict-zone bulletins for airspace, and NGA navigational warnings at sea." },
    { id: "elements", name: "Elements", href: "https://elements.theintelligence.company", status: "beta", group: "layers",
      label: "Land and maritime · natural hazards",
      short: "Natural hazards as the authorities report them.",
      long: "Natural hazards as the authorities report them: earthquakes with impact alerts, volcano alert levels, satellite fire detections, multi-hazard alerts, hurricane-center storms and disaster mapping on one map." },
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
  var GROUPS = [["layers", "Across the layers"], ["tools", "Other tools"]];

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

  var mounted = false;
  function mount(target) {
    if (mounted) return;
    mounted = true;
    var here = currentId();
    var nav = el("nav", "tic-house");
    nav.setAttribute("aria-label", "The Intelligence Company");
    var inner = el("div", "tic-house-in");
    var home = el("a", "tic-house-home");
    home.href = HOME;
    home.append(el("span", "tic-house-arrow", "←"), " The Intelligence Company");
    home.firstChild.setAttribute("aria-hidden", "true");

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

    var items = [];
    function show(p, a) {
      dName.textContent = p.name;
      dMeta.textContent = p.label + " · " + STATUS[p.status] + (p.id === here ? " · you are here" : "");
      dLong.textContent = p.long;
      items.forEach(function (x) { x.classList.toggle("on", x === a); });
    }
    GROUPS.forEach(function (g) {
      list.append(el("p", "tic-house-group", g[1]));
      var ul = el("ul", "tic-house-ul");
      PROGRAMS.filter(function (p) { return p.group === g[0]; }).forEach(function (p) {
        var li = el("li");
        var a = el("a", "tic-house-item");
        a.href = p.href;
        var nameRow = el("span", "tic-house-name", p.name);
        if (p.id === here) {
          a.setAttribute("aria-current", "page");
          a.classList.add("here");
          nameRow.append(el("span", "tic-house-here", "You are here"));
        }
        a.append(nameRow, el("span", "tic-house-st st-" + p.status, STATUS[p.status]),
          el("span", "tic-house-label", p.label), el("span", "tic-house-short", p.short));
        var desc = el("span", "tic-house-sr", p.long);
        desc.id = "tic-house-d-" + p.id;
        a.setAttribute("aria-describedby", desc.id);
        a.addEventListener("mouseenter", function () { show(p, a); });
        a.addEventListener("focus", function () { show(p, a); });
        li.append(a, desc);
        ul.append(li);
        items.push(a);
        a._p = p;
      });
      list.append(ul);
    });
    cols.append(list, detail);
    var all = el("a", "tic-house-all", "How the programs fit together, and what's planned →");
    all.href = ALL;
    panel.append(cols, all);
    menu.append(btn, panel);
    inner.append(home, menu);
    nav.append(inner);

    function open() {
      panel.hidden = false;
      btn.setAttribute("aria-expanded", "true");
      var start = items.filter(function (a) { return a._p.id === here; })[0] || items[0];
      show(start._p, start);
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
    if (slot) slot.append(nav); else document.body.insertBefore(nav, document.body.firstChild);
  }

  window.TicNav = { version: "1.1", programs: PROGRAMS.slice(), mount: mount };
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", function () { mount(); });
})();
