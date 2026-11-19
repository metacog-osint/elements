/*! tic-fold.js v1.1 · The Intelligence Company: a long table or list shows its first rows and "Show all N" ·
 *  canonical copy: the hub's site/shared/tic-fold.js (copy into each site with
 *  tic-fold.css; keep the version line).
 *  SPDX-License-Identifier: MIT. Copyright (c) 2026 The Intelligence Company. MIT in every repository it is
 *  copied into, whatever that repository's own licence.
 *
 *  From the 18 Nov 2026 page-length survey: with the sections row in place, tables of 40 to 85 rows still made the
 *  light pages 14,000-18,000 px tall on a desktop (Relief 31,000 px on a phone). Cordon folded its long tables on
 *  phones with its own code; this is that fold, shared, at every width.
 *
 *  Use: mark the table or list. The site keeps ordering its rows (flagged and most recent first); this module
 *  never reorders, it only folds what comes after the first rows.
 *    <table data-tic-fold> ... </table>          first 10 rows on phones (<= 760 px), first 15 wider
 *    <ul data-tic-fold="8"> ... </ul>             8 everywhere
 *    <div data-tic-fold="10 25"> ...cards </div>   10 on phones, 25 wider; any element's children are its items
 *    data-tic-fold-find                           adds "Find in this table" over a list of 25 or more
 *  A table's items are its body rows; anything else's are its element children. It folds only when at least
 *  3 more items than the first rows would be hidden, so it never hides one or two.
 *  The button goes after the element, or after its wrapper when the element is the wrapper's only child (a
 *  sideways-scrolling box such as <div class="scroll">).
 *  A site that redraws the element (innerHTML on a filter or a refresh) needs nothing more: the fold re-applies,
 *  and an opened fold stays open. An element added later is found as well. A link to a row (#breakup-12345)
 *  opens the fold, any closed <details> around it and, on a page with tic-tabs.js, the row's group, even when the
 *  site draws the row after the page has loaded (1.1: the <details>, for Cordon's travel lists). Printing shows every row. Without script, every row shows.
 *  Hidden rows are display: none, so the browser's own find does not reach them; "Show all" is one press away and
 *  data-tic-fold-find searches every row.
 *  No inline styles, no HTML strings (works under style-src 'self'); nothing is stored. Nothing moves.
 */
(function () {
  "use strict";
  var PHONE = "(max-width: 760px)";
  var MIN_HIDDEN = 3;
  var FIND_MIN = 25;
  var mq = window.matchMedia ? window.matchMedia(PHONE) : { matches: false };
  var all = [];
  var seq = 0;

  function counts(el) {
    var v = (el.getAttribute("data-tic-fold") || "").trim().split(/\s+/).map(Number).filter(function (n) { return n > 0; });
    if (!v.length) return [10, 15];
    return [v[0], v.length > 1 ? v[1] : v[0]];
  }

  function items(el) {
    if (el.tagName === "TABLE") {
      var out = [];
      if (el.tBodies.length) {
        for (var b = 0; b < el.tBodies.length; b++) out.push.apply(out, el.tBodies[b].rows);
      } else {
        for (var r = 0; r < el.rows.length; r++) if (!el.rows[r].closest("thead")) out.push(el.rows[r]);
      }
      return out;
    }
    return Array.prototype.filter.call(el.children, function (c) { return !c.classList.contains("tic-fold-ui"); });
  }

  function word(el) { return el.tagName === "TABLE" ? "rows" : "items"; }

  function setup(el) {
    if (el._ticFold) return el._ticFold;
    el.classList.add("tic-fold-seen");
    if (!el.id) el.id = "tic-fold-" + (++seq);
    var anchor = el;
    var p = el.parentElement;
    if (p && p.children.length === 1 && p !== document.body && p.tagName !== "MAIN" && p.tagName !== "SECTION") anchor = p;

    var bar = document.createElement("div");
    bar.className = "tic-fold-bar";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tic-fold-more";
    btn.setAttribute("aria-controls", el.id);
    btn.setAttribute("aria-expanded", "false");
    var note = document.createElement("span");
    note.className = "tic-fold-note";
    note.setAttribute("aria-live", "polite");
    bar.appendChild(btn);
    bar.appendChild(note);
    anchor.parentNode.insertBefore(bar, anchor.nextSibling);

    var find = null;
    if (el.hasAttribute("data-tic-fold-find")) {
      var lab = document.createElement("label");
      lab.className = "tic-fold-find";
      var span = document.createElement("span");
      span.textContent = el.tagName === "TABLE" ? "Find in this table" : "Find in this list";
      find = document.createElement("input");
      find.type = "search";
      find.setAttribute("aria-controls", el.id);
      lab.appendChild(span);
      lab.appendChild(find);
      anchor.parentNode.insertBefore(lab, anchor);
      find.addEventListener("input", function () { apply(); });
    }

    var st = { el: el, open: false, bar: bar, btn: btn, note: note, find: find, label: find && find.parentNode };

    function apply() {
      var list = items(el);
      var n = list.length;
      var first = counts(el)[mq.matches ? 0 : 1];
      var q = find ? find.value.trim().toLowerCase() : "";
      if (st.label) st.label.hidden = n < FIND_MIN && !q;
      var matched = 0;
      list.forEach(function (it) {
        var miss = !!q && it.textContent.toLowerCase().indexOf(q) < 0;
        it.classList.toggle("tic-fold-miss", miss);
        if (!miss) matched++;
      });
      var fold = !q && n - first >= MIN_HIDDEN;
      list.forEach(function (it, i) { it.classList.toggle("tic-fold-x", fold && !st.open && i >= first); });
      el.classList.toggle("tic-fold-on", fold && !st.open);
      btn.hidden = !fold;
      btn.setAttribute("aria-expanded", st.open ? "true" : "false");
      btn.textContent = st.open ? "Show the first " + first : "Show all " + n;
      note.textContent = q ? matched + " of " + n + " " + word(el) + " match"
        : fold && !st.open ? "Showing " + first + " of " + n : "";
      bar.hidden = !fold && !q;
    }

    btn.addEventListener("click", function () {
      st.open = !st.open;
      apply();
      if (!st.open) {
        var top = el.getBoundingClientRect().top;
        if (top < 0) el.scrollIntoView({ block: "start" });
      }
    });

    var queued = false;
    var obs = new MutationObserver(function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; apply(); fromHash(); });
    });
    obs.observe(el, { childList: true, subtree: true });

    st.apply = apply;
    st.show = function () { st.open = true; apply(); };
    el._ticFold = st;
    all.push(st);
    apply();
    return st;
  }

  // A link to a row in a marked element opens its fold and, inside a tic-tabs.js sections row, its group, then
  // scrolls to the row. Sites draw their rows after the page loads, so this runs again as rows arrive, once per
  // address: a later redraw (a filter, a refresh) never pulls the page back to the row.
  var handled = null;
  function fromHash(force) {
    var h = location.hash || "";
    if (h.length < 2 || (!force && handled === h)) return;
    var id;
    try { id = decodeURIComponent(h.slice(1)); } catch (e) { return; }
    var t = document.getElementById(id);
    if (!t) return;
    var st = null;
    for (var i = 0; i < all.length; i++) if (all[i].el !== t && all[i].el.contains(t)) { st = all[i]; break; }
    if (!st) return;
    handled = h;
    st.apply();  // another element's redraw can get here first, before this element has folded its new rows
    if (t.closest(".tic-fold-x")) st.show();
    var g = t.closest("[data-tab-label]");
    var tabs = g && g.parentElement && g.parentElement._ticTabs;
    if (tabs && g.hidden) tabs.show(g.id);
    for (var d = t.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) d.open = true;
    t.scrollIntoView({ block: "start" });
    // Other folds above the row settle in this same frame; land on the row again once they have.
    requestAnimationFrame(function () { if (location.hash === h) t.scrollIntoView({ block: "start" }); });
  }

  function scan(root) {
    var els = (root || document).querySelectorAll("[data-tic-fold]");
    for (var i = 0; i < els.length; i++) setup(els[i]);
  }

  var later = false;
  function watch() {
    new MutationObserver(function () {
      if (later) return;
      later = true;
      requestAnimationFrame(function () {
        later = false;
        if (document.querySelector("[data-tic-fold]:not(.tic-fold-seen)")) { scanNew(); fromHash(); }
      });
    }).observe(document.body, { childList: true, subtree: true });
  }
  function scanNew() {
    var els = document.querySelectorAll("[data-tic-fold]:not(.tic-fold-seen)");
    for (var i = 0; i < els.length; i++) { els[i].classList.add("tic-fold-seen"); setup(els[i]); }
  }

  function start() {
    scanNew();
    watch();
    fromHash();
    window.addEventListener("hashchange", function () { fromHash(true); });
    var onChange = function () { all.forEach(function (s) { s.apply(); }); };
    if (mq.addEventListener) mq.addEventListener("change", onChange); else if (mq.addListener) mq.addListener(onChange);
  }

  window.TicFold = { version: "1.1", setup: setup, scan: scanNew };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
