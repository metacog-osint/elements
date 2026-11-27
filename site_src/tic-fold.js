/*! tic-fold.js v2.4 · The Intelligence Company: a long table or list opens in a scrolling window about ten rows
 *  tall, its header kept in view, with "Show all N" beside it ·
 *  canonical copy: the hub's site/shared/tic-fold.js (copy into each site with
 *  tic-fold.css; keep the version line).
 *  SPDX-License-Identifier: MIT. Copyright (c) 2026 The Intelligence Company. MIT in every repository it is
 *  copied into, whatever that repository's own licence.
 *
 *  From the 18 Nov 2026 page-length survey: with the sections row in place, tables of 40 to 85 rows still made the
 *  light pages 14,000-18,000 px tall on a desktop (Relief 31,000 px on a phone). 1.x cut a long table to its first
 *  rows behind "Show all". 2.0 (20 Nov 2026, the rule for long lists on every site): the table opens in a window
 *  about ten rows tall that scrolls, every row stays in the page (so the browser's find reaches it), and "Show all N"
 *  lifts the limit. Blackout's own table window (blackout#24) was the model.
 *
 *  Use: mark the table or list. The site keeps ordering its rows (flagged and most recent first); this module
 *  never reorders.
 *    <table data-tic-fold> ... </table>          a window about 10 rows tall, at every width
 *    <ul data-tic-fold="8"> ... </ul>             8 rows tall
 *    <div data-tic-fold="6 12"> ...cards </div>    6 on phones (<= 760 px), 12 wider; any element's children are its items
 *    data-tic-fold-find                           adds "Find in this table" over a list of 25 or more
 *  A table's items are its body rows; anything else's are its element children. It makes a window only when at
 *  least 3 more items than the window holds would sit below it, so it never boxes up a list one or two rows over.
 *  The window is the element's wrapper when the element is a <div>'s only child (a sideways-scrolling box such as
 *  <div class="scroll">); otherwise the module wraps the element in <div class="tic-fold-box">. The window is
 *  focusable (arrow keys scroll it) and is a named region with its row count. A table's header row stays in view
 *  while the window scrolls. Its height is measured from the rows themselves, so ten tall cards make a taller
 *  window than ten short rows; it never runs past three quarters of the screen. The button goes after the window.
 *  A site that redraws the element (innerHTML on a filter or a refresh) needs nothing more: the window re-applies,
 *  and one opened with "Show all" stays open, even when the site draws a new element in its place, if the element
 *  has an id or a table has a caption (numbers in the caption are set aside). An element added later is found
 *  as well. A link to a row (#breakup-12345) scrolls its window to the row and the page to the window, and opens
 *  any closed <details> around it and, on a page with tic-tabs.js, the row's group, even when the site draws the
 *  row after the page has loaded. Printing shows every row. Without script, every row shows.
 *  No HTML strings; the measured height is set through the element's style object (CSSOM), which a CSP of
 *  style-src 'self' allows; nothing is stored. Nothing moves.
 *  From 1.x: the default is 10 at every width (was 10 on phones, 15 wider); "Show the first N" is now
 *  "Show in a window"; the classes tic-fold-on and tic-fold-x are gone.
 *  2.1: a row the site marks `hidden` (its own search or filter) is left out of the count and the window, and
 *  hiding or showing one re-applies the window.
 *  2.2 (21 Nov 2026): after a link lands on a row, the second landing a frame later runs only if the layout
 *  moved. It used to run regardless, and pulled back a reader who had scrolled in that frame.
 *  2.3 (21 Nov 2026): a box that is not a window but scrolls sideways (a wide table on a phone) is focusable too,
 *  a named region, so a keyboard reader can scroll it (axe scrollable-region-focusable). It is checked again when
 *  the width changes or a tic-tabs group is shown.
 *  2.4: the same check runs when the box is first drawn, so a wide table in a tab the site hides and shows itself
 *  (not a tic-tabs group) is focusable at once, not only after the window is resized.
 */
(function () {
  "use strict";
  var PHONE = "(max-width: 760px)";
  var MIN_BELOW = 3;
  var FIND_MIN = 25;
  var PEEK = 0.5;  // half of the next row shows at the window's foot, so it reads as a list that goes on
  var mq = window.matchMedia ? window.matchMedia(PHONE) : { matches: false };
  var all = [];
  var seq = 0;
  var opened = {};  // windows the reader opened in full, by key, so a redraw keeps them open

  function counts(el) {
    var v = (el.getAttribute("data-tic-fold") || "").trim().split(/\s+/).map(Number).filter(function (n) { return n > 0; });
    if (!v.length) return [10, 10];
    return [v[0], v.length > 1 ? v[1] : v[0]];
  }

  function shown(it) { return !it.hidden; }

  function items(el) {
    if (el.tagName === "TABLE") {
      var out = [];
      if (el.tBodies.length) {
        for (var b = 0; b < el.tBodies.length; b++) out.push.apply(out, el.tBodies[b].rows);
      } else {
        for (var r = 0; r < el.rows.length; r++) if (!el.rows[r].closest("thead")) out.push(el.rows[r]);
      }
      return out.filter(shown);
    }
    return Array.prototype.slice.call(el.children).filter(shown);
  }

  function word(el) { return el.tagName === "TABLE" ? "rows" : "items"; }

  function keyOf(el) {
    if (el.id && !/^tic-fold-\d+$/.test(el.id)) return "#" + el.id;
    var cap = el.tagName === "TABLE" && el.caption ? el.caption.textContent.trim() : "";
    return cap ? "cap:" + cap.replace(/[\d,.]+/g, "#") : null;
  }

  // The window's name: the table's caption, the element's own label, else the nearest heading before it.
  function nameOf(el, box) {
    if (el.tagName === "TABLE" && el.caption && el.caption.textContent.trim()) return el.caption.textContent.trim();
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    var by = el.getAttribute("aria-labelledby");
    var lab = by && document.getElementById(by.split(/\s+/)[0]);
    if (lab && lab.textContent.trim()) return lab.textContent.trim();
    for (var n = box, up = 0; n && up < 4; n = n.parentElement, up++) {
      for (var s = n.previousElementSibling; s; s = s.previousElementSibling) {
        if (/^H[1-6]$/.test(s.tagName) && s.textContent.trim()) return s.textContent.trim();
      }
    }
    return el.tagName === "TABLE" ? "Table" : "List";
  }

  function setup(el) {
    if (el._ticFold) return el._ticFold;
    el.classList.add("tic-fold-seen");
    if (!el.id) el.id = "tic-fold-" + (++seq);
    var box = el.parentElement;
    if (!(box && box.tagName === "DIV" && box.children.length === 1 && !box.hasAttribute("data-tab-label")
      && !box.hasAttribute("data-tic-tabs"))) {
      box = document.createElement("div");
      el.parentNode.insertBefore(box, el);
      box.appendChild(el);
    }
    box.classList.add("tic-fold-box");

    var bar = document.createElement("div");
    bar.className = "tic-fold-bar";
    var note = document.createElement("span");
    note.className = "tic-fold-note";
    note.setAttribute("aria-live", "polite");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tic-fold-more";
    btn.setAttribute("aria-controls", el.id);
    btn.setAttribute("aria-expanded", "false");
    bar.appendChild(btn);
    bar.appendChild(note);
    box.parentNode.insertBefore(bar, box.nextSibling);

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
      box.parentNode.insertBefore(lab, box);
      find.addEventListener("input", function () { apply(); });
    }

    var key = keyOf(el);
    var st = { el: el, box: box, open: !!(key && opened[key]), win: false, bar: bar, btn: btn, note: note, find: find,
      label: find && find.parentNode };

    // The window's height: down to the foot of its last row, plus a peek at the next. Measured only while the
    // window is drawn (a closed <details> or a hidden group measures nothing and keeps the stylesheet's fallback).
    function measure() {
      if (!st.win || st.open) return;
      var list = items(el).filter(function (it) { return !it.classList.contains("tic-fold-miss"); });
      var rows = counts(el)[mq.matches ? 0 : 1];
      if (list.length <= rows) return;
      var last = list[rows - 1].getBoundingClientRect();
      var next = list[rows].getBoundingClientRect();
      if (!last.height) return;
      var cs = getComputedStyle(box);
      var b = box.getBoundingClientRect();
      var px = function (v) { return parseFloat(v) || 0; };
      var h = last.bottom + next.height * PEEK - b.top + box.scrollTop;
      if (cs.boxSizing !== "border-box") h -= px(cs.borderTopWidth) + px(cs.paddingTop);
      else h += px(cs.borderBottomWidth) + px(cs.paddingBottom);
      h = Math.round(h);
      if (Math.abs(h - (st.h || 0)) > 1) { st.h = h; box.style.setProperty("--tic-fold-h", h + "px"); }
      var head = el.tagName === "TABLE" && el.tHead ? Math.round(el.tHead.getBoundingClientRect().height) : 0;
      if (head !== st.head) { st.head = head; box.style.setProperty("--tic-fold-head", head + "px"); }
    }

    // Whether a box that is not a window scrolls sideways now. A box that is not drawn (a hidden tab) measures no
    // overflow, so this is read again once its size changes.
    function sideways() { return box.scrollWidth > box.clientWidth + 1; }

    function apply() {
      var list = items(el);
      var n = list.length;
      var rows = counts(el)[mq.matches ? 0 : 1];
      var q = find ? find.value.trim().toLowerCase() : "";
      if (st.label) st.label.hidden = n < FIND_MIN && !q;
      var matched = 0;
      list.forEach(function (it) {
        var miss = !!q && it.textContent.toLowerCase().indexOf(q) < 0;
        it.classList.toggle("tic-fold-miss", miss);
        if (!miss) matched++;
      });
      var win = matched - rows >= MIN_BELOW;
      st.win = win;
      var boxed = win && !st.open;
      box.classList.toggle("tic-fold-win", boxed);
      var wide = !boxed && sideways();
      st.wide = wide;
      if (boxed || wide) {
        box.setAttribute("tabindex", "0");
        box.setAttribute("role", "region");
        box.setAttribute("aria-label", nameOf(el, box) + ": " + matched + " " + word(el) + (boxed ? ", in a window that scrolls" : ", scrolls sideways"));
      } else {
        box.removeAttribute("tabindex");
        box.removeAttribute("role");
        box.removeAttribute("aria-label");
      }
      btn.hidden = !win;
      btn.setAttribute("aria-expanded", st.open ? "true" : "false");
      btn.textContent = st.open ? "Show in a window" : "Show all " + matched;
      note.textContent = q ? matched + " of " + n + " " + word(el) + " match"
        : boxed ? "About " + rows + " of " + n + " in view; scroll for the rest" : "";
      bar.hidden = !win && !q;
      measure();
    }

    btn.addEventListener("click", function () {
      st.open = !st.open;
      var k = keyOf(el);
      if (k) { if (st.open) opened[k] = true; else delete opened[k]; }
      apply();
      if (!st.open) {
        box.scrollTop = 0;
        if (box.getBoundingClientRect().top < 0) box.scrollIntoView({ block: "start" });
      }
    });

    var queued = false;
    var obs = new MutationObserver(function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; apply(); fromHash(); });
    });
    obs.observe(el, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });

    // A window drawn later (a <details> opened, a group shown) or narrowed (rows wrap taller) measures again.
    if (window.ResizeObserver) {
      var rq = false;
      new ResizeObserver(function () {
        if (rq) return;
        rq = true;
        requestAnimationFrame(function () {
          rq = false;
          measure();
          // A box drawn for the first time (a tab of the site's own, with no tic-tabs event) may now scroll sideways.
          if (!(st.win && !st.open) && sideways() !== !!st.wide) apply();
        });
      }).observe(box);
    }

    st.apply = apply;
    st.measure = measure;
    el._ticFold = st;
    all.push(st);
    apply();
    return st;
  }

  // A link to a row in a marked element opens, inside a tic-tabs.js sections row, its group and any closed
  // <details> around it, then scrolls the window to the row (just under the header row) and the page to it.
  // Sites draw their rows after the page loads, so this runs again as rows arrive, once per address: a later
  // redraw (a filter, a refresh) never pulls the page back to the row.
  var handled = null;
  function placeOf(t, box) { return t.getBoundingClientRect().top + window.scrollY + box.scrollTop; }
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
    if (st.find && t.closest(".tic-fold-miss")) st.find.value = "";
    var g = t.closest("[data-tab-label]");
    var tabs = g && g.parentElement && g.parentElement._ticTabs;
    if (tabs && g.hidden) tabs.show(g.id);
    for (var d = t.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) d.open = true;
    st.apply();  // measures now that the window is drawn; another element's redraw can get here first
    t.scrollIntoView({ block: "start" });
    // Other windows above the row settle in this same frame; land on the row again once they have. A move that
    // only scrolled (the row's place in the page is unchanged) is the reader's, and stays.
    var y = window.scrollY, inner = st.box.scrollTop, place = placeOf(t, st.box);
    requestAnimationFrame(function () {
      if (location.hash !== h) return;
      var scrolled = window.scrollY !== y || st.box.scrollTop !== inner;
      if (scrolled && Math.abs(placeOf(t, st.box) - place) < 1) return;
      t.scrollIntoView({ block: "start" });
    });
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
    // Web fonts and images change row heights after the first measure.
    window.addEventListener("load", function () { all.forEach(function (s) { s.measure(); }); });
    // A box's sideways overflow depends on the width and on its group being shown.
    var again = false;
    var recheck = function () {
      if (again) return;
      again = true;
      requestAnimationFrame(function () { again = false; all.forEach(function (s) { s.apply(); }); });
    };
    window.addEventListener("resize", recheck);
    document.addEventListener("tic-tabs:show", recheck);
  }

  window.TicFold = { version: "2.4", setup: setup, scan: scanNew };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
