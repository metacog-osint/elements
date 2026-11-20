/*! tic-tabs.js v1.0 · The Intelligence Company: one section at a time on phones, a section row everywhere ·
 *  canonical copy: the hub's site/shared/tic-tabs.js (copy into each site with
 *  tic-tabs.css; keep the version line).
 *  SPDX-License-Identifier: MIT. Copyright (c) 2026 The Intelligence Company. MIT in every repository it is
 *  copied into, whatever that repository's own licence.
 *
 *  From the suite design review (15 Nov 2026, "C · Shell"): the light program pages stacked every section, so a
 *  phone page ran to dozens of screens (Cordon 36,195 px). Group the sections below the map, and this module adds a
 *  sticky row of links to the groups ("Sections on this page"). On a phone it shows one group at a time; on a wider
 *  screen every group stays on the page and the row jumps to it. Without script, every group shows.
 *
 *  Use:
 *    <div data-tic-tabs>
 *      <div id="sec-air" data-tab-label="Air"> ...cards... </div>
 *      <div id="sec-sea" data-tab-label="Sea"> ...cards... </div>
 *    </div>
 *  data-tic-tabs="(max-width: 760px)" sets when one group shows at a time (that media query is the default).
 *  A link to a group or to anything inside one (#health-h) opens that group. Each group needs an id.
 *  A site with a map or chart inside a group listens for "tic-tabs:show" on the group to redraw it.
 *  Links and aria-current, not ARIA tabs: each group is a section of the page and keeps its own headings, so a
 *  screen reader's heading list still holds the page, and a link can be opened, shared and bookmarked.
 *  No inline styles, no HTML strings; nothing is stored. Nothing moves, so reduced motion needs nothing.
 */
(function () {
  "use strict";
  var PHONE = "(max-width: 760px)";

  function groupOf(box, el) {
    while (el && el.parentElement !== box) el = el.parentElement;
    return el && el.hasAttribute("data-tab-label") ? el : null;
  }

  function setup(box) {
    if (box._ticTabs) return box._ticTabs;
    var groups = Array.prototype.filter.call(box.children, function (g) { return g.hasAttribute("data-tab-label") && g.id; });
    if (groups.length < 2) return null;
    var mq = window.matchMedia ? window.matchMedia(box.getAttribute("data-tic-tabs") || PHONE) : { matches: false };
    var nav = document.createElement("nav");
    nav.className = "tic-tabs-nav";
    nav.setAttribute("aria-label", "Sections on this page");
    var ul = document.createElement("ul");
    var links = groups.map(function (g) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + g.id;
      a.textContent = g.getAttribute("data-tab-label");
      li.appendChild(a);
      ul.appendChild(li);
      return a;
    });
    nav.appendChild(ul);
    box.parentNode.insertBefore(nav, box);
    box.classList.add("tic-tabs-on");

    var current = groups[0];
    function apply() {
      var one = mq.matches;
      box.classList.toggle("tic-tabs-one", one);
      groups.forEach(function (g, i) {
        var on = g === current;
        g.hidden = one && !on;
        if (one && on) links[i].setAttribute("aria-current", "true"); else links[i].removeAttribute("aria-current");
      });
    }
    function show(g, focusEl) {
      var was = current;
      current = g;
      apply();
      if (mq.matches && was !== g) {
        try { g.dispatchEvent(new CustomEvent("tic-tabs:show", { bubbles: true })); } catch (e) { /* old browsers */ }
      }
      if (focusEl) focusEl.scrollIntoView({ block: "start" });
    }
    function fromHash() {
      var id = decodeURIComponent((location.hash || "").slice(1));
      if (!id) return false;
      var el = document.getElementById(id);
      var g = el && groupOf(box, el);
      if (!g) return false;
      show(g, mq.matches ? (el === g ? null : el) : null);
      if (mq.matches && el === g) toTop();
      return true;
    }
    // On a phone, a new group starts just under the row; never jump down the page to get there.
    function toTop() {
      var navTop = nav.getBoundingClientRect().top;
      var house = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--tic-house-h")) || 0;
      if (navTop <= house + 1) window.scrollBy(0, box.getBoundingClientRect().top - house - nav.offsetHeight);
    }

    links.forEach(function (a, i) {
      a.addEventListener("click", function (ev) {
        if (!mq.matches) return;  // wider screens: an ordinary jump to the group
        ev.preventDefault();
        show(groups[i]);
        toTop();
        try { history.replaceState(null, "", "#" + groups[i].id); } catch (e) { /* file: pages */ }
        a.focus();
      });
    });
    window.addEventListener("hashchange", fromHash);
    var onChange = function () { apply(); };
    if (mq.addEventListener) mq.addEventListener("change", onChange); else if (mq.addListener) mq.addListener(onChange);
    apply();
    fromHash();
    var api = { show: function (id) { var g = document.getElementById(id); if (g && groupOf(box, g) === g) show(g); },
      current: function () { return current.id; }, nav: nav };
    box._ticTabs = api;
    return api;
  }

  function setupAll() {
    var boxes = document.querySelectorAll("[data-tic-tabs]");
    for (var i = 0; i < boxes.length; i++) setup(boxes[i]);
  }

  window.TicTabs = { version: "1.0", setup: setup };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setupAll); else setupAll();
})();
