/* app.js - What the app does: tabs, chapters, search, jump links and "copy LaTeX".
   In V2 the formulas are not in the page: auth.js logs you in, downloads them
   from the database and then calls startFormulaApp(DATA) below.

   How the page is organised:
     tab (one per folder in latex/, e.g. Math)
       chapter button (one per .tex file, e.g. Calculus)
         section heading + its formula cards */
window.startFormulaApp = function (DATA) {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var list = $("list"), q = $("q"), tabsEl = $("tabs"), chaptersEl = $("chapters"), jumpEl = $("jump");
  var countEl = $("count"), emptyEl = $("empty"), footEl = $("foot");

  // Lowercase and remove accents, so "Archimedes" and "archimédes" match.
  function norm(s) {
    return (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  // "Algebra & Complex Numbers" -> "algebra-complex-numbers" (used in links: #calculus)
  function slug(s) {
    return norm(s).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  // ---------- 1. Chapters: one per .tex file ----------
  var chapters = {};            // chapter id -> { id, name, slug, sheet, sections, cards }
  DATA.sheets.forEach(function (sheet) {
    (sheet.chapters || []).forEach(function (c) {
      chapters[c.id] = { id: c.id, name: c.name, slug: slug(c.name), sheet: sheet, sections: [], cards: 0 };
    });
    sheet.sections.forEach(function (section) {
      var c = chapters[section.chapter];
      if (c) { c.sections.push(section); c.cards += section.cards.length; }
    });
  });
  // "Math · Calculus" for chapters with several sections, just "Math" otherwise
  // (a one-section chapter is named after its section already).
  function place(sheet, section) {
    var c = chapters[section.chapter];
    return sheet.name + (c && c.sections.length > 1 ? " · " + c.name : "");
  }

  // ---------- 2. Build every section header and card once ----------
  // entries holds one object per header/card, in the order of your LaTeX files.
  var entries = [];

  DATA.sheets.forEach(function (sheet) {
    sheet.sections.forEach(function (section) {
      var head = el("div", "sec");
      head.id = section.id;
      head.style.setProperty("--sec", section.color);
      head.appendChild(el("p", "sec-sheet", place(sheet, section)));
      var h2 = el("h2", null, section.title_html);
      h2.insertBefore(el("span", "dot"), h2.firstChild);
      head.appendChild(h2);
      if (section.intro_html) head.appendChild(el("div", "sec-intro", section.intro_html));
      list.appendChild(head);
      entries.push({ kind: "section", el: head, sheet: sheet, section: section, order: entries.length });

      section.cards.forEach(function (card) {
        var art = el("article", "card");
        art.id = card.id;
        art.style.setProperty("--sec", section.color);

        var top = el("div", "card-head");
        top.appendChild(el("h3", null, card.title_html));
        var copy = el("button", "copy", "TeX");
        copy.type = "button";
        copy.title = "Copy the LaTeX source of this card";
        copy.setAttribute("aria-label", "Copy LaTeX of " + card.title_text);
        copy.addEventListener("click", function () { copyText(card.latex, copy); });
        top.appendChild(copy);
        art.appendChild(top);

        var crumb = el("p", "crumb");
        crumb.appendChild(el("span", "dot"));
        crumb.appendChild(document.createTextNode(place(sheet, section) + " · " + section.title_text));
        art.appendChild(crumb);
        art.appendChild(el("div", "card-body", card.body_html));
        list.appendChild(art);

        var c = chapters[section.chapter];
        entries.push({
          kind: "card", el: art, sheet: sheet, section: section, order: entries.length,
          // what the search looks at, from most to least important:
          t: norm(card.title_text),
          s: norm(section.title_text + " " + (c ? c.name : "") + " " + sheet.name),
          b: norm(card.body_text),
        });
      });
    });
  });

  // ---------- 3. Search ----------
  // Searches ALL tabs and chapters. Every word you type must appear somewhere
  // in the card. Words in the title count most, then the section/chapter/tab
  // name, then the formula and explanation.
  function score(e, words, phrase) {
    var s = 0;
    if (e.t.indexOf(phrase) !== -1) s += 20;
    if (e.t.indexOf(phrase) === 0) s += 10;
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (e.t.indexOf(w) !== -1) s += 6;
      else if (e.s.indexOf(w) !== -1) s += 3;
      else if (e.b.indexOf(w) !== -1) s += 1;
      else return 0;
    }
    return s;
  }

  // ---------- 4. Tabs and chapter buttons ----------
  // current.chapter is "all" or a chapter id.
  var current = { sheet: DATA.sheets.length ? DATA.sheets[0].id : "", chapter: "all" };

  // A link or saved choice can be a tab ("#physics") or a chapter ("#statics").
  function findPlace(key) {
    if (!key) return null;
    for (var i = 0; i < DATA.sheets.length; i++) {
      if (DATA.sheets[i].id === key) return { sheet: key, chapter: "all" };
    }
    for (var id in chapters) {
      if (chapters[id].slug === key) return { sheet: chapters[id].sheet.id, chapter: id };
    }
    return null;
  }
  var saved = null;
  try { saved = localStorage.getItem("formula-v2-place"); } catch (err) { /* storage blocked */ }
  current = findPlace((location.hash || "").slice(1)) || findPlace(saved) || current;

  DATA.sheets.forEach(function (sheet) {
    var n = sheet.sections.reduce(function (sum, sec) { return sum + sec.cards.length; }, 0);
    var b = el("button", "tab", sheet.name + '<span class="n">' + n + "</span>");
    b.type = "button";
    b.id = "tab-" + sheet.id;
    b.setAttribute("role", "tab");
    b.addEventListener("click", function () { select(sheet.id, "all"); });
    tabsEl.appendChild(b);
  });

  function select(sheetId, chapterId) {
    current = { sheet: sheetId, chapter: chapterId };
    var key = chapterId === "all" ? sheetId : chapters[chapterId].slug;
    try { localStorage.setItem("formula-v2-place", key); } catch (err) { /* ignore */ }
    try { history.replaceState(null, "", "#" + key); } catch (err) { /* ignore */ }
    if (q.value) q.value = "";            // picking a tab or chapter ends a search
    apply();
    window.scrollTo(0, 0);
  }

  function chip(label, count, color, pressed, onClick) {
    var b = el("button");
    b.type = "button";
    if (color) {
      b.style.setProperty("--sec", color);
      b.appendChild(el("span", "dot"));
    }
    b.appendChild(document.createTextNode(label));
    if (count != null) b.appendChild(el("span", "n", String(count)));
    if (pressed != null) b.setAttribute("aria-pressed", String(pressed));
    b.addEventListener("click", onClick);
    return b;
  }

  function renderChapters() {
    chaptersEl.innerHTML = "";
    var sheet = DATA.sheets.filter(function (s) { return s.id === current.sheet; })[0];
    if (!sheet || !(sheet.chapters || []).length) return;
    var total = sheet.sections.reduce(function (sum, sec) { return sum + sec.cards.length; }, 0);
    chaptersEl.appendChild(chip("All", total, null, current.chapter === "all",
      function () { select(sheet.id, "all"); }));
    sheet.chapters.forEach(function (c) {
      var info = chapters[c.id];
      chaptersEl.appendChild(chip(c.name, info.cards, info.sections[0] && info.sections[0].color,
        current.chapter === c.id, function () { select(sheet.id, c.id); }));
    });
  }

  // Section buttons above the list, for chapters with several sections (Calculus, Statics).
  function renderJump(searching) {
    jumpEl.innerHTML = "";
    var c = chapters[current.chapter];
    jumpEl.hidden = searching || !c || c.sections.length < 2;
    if (jumpEl.hidden) return;
    c.sections.forEach(function (section) {
      jumpEl.appendChild(chip(section.title_text, null, section.color, null, function () {
        $(section.id).scrollIntoView();
      }));
    });
  }

  // ---------- 5. Show / hide everything for the current place + search ----------
  function apply() {
    var phrase = norm(q.value.trim());
    var words = phrase.split(/\s+/).filter(Boolean);
    var searching = words.length > 0;
    var shown = 0, ranked = [];
    list.classList.toggle("searching", searching);

    entries.forEach(function (e) {
      var visible = e.sheet.id === current.sheet &&
        (current.chapter === "all" || e.section.chapter === current.chapter);
      e.el.style.order = e.order;
      if (e.kind === "section") { e.el.hidden = searching || !visible; return; }
      if (!searching) { e.el.hidden = !visible; if (visible) shown++; return; }
      var s = score(e, words, phrase);
      e.el.hidden = !s;
      if (s) ranked.push([s, e]);
    });

    if (searching) {
      ranked.sort(function (a, b) { return b[0] - a[0] || a[1].order - b[1].order; });
      ranked.forEach(function (r, i) { r[1].el.style.order = i; });
      shown = ranked.length;
    }

    DATA.sheets.forEach(function (sheet) {
      $("tab-" + sheet.id).setAttribute("aria-selected", String(!searching && sheet.id === current.sheet));
    });
    chaptersEl.hidden = searching;
    if (!searching) renderChapters();
    renderJump(searching);
    countEl.textContent = searching
      ? shown + (shown === 1 ? " match" : " matches") + " in all tabs"
      : shown + " formulas";
    renderEmpty(shown, q.value.trim());
  }

  function renderEmpty(shown, query) {
    emptyEl.hidden = shown > 0;
    if (shown > 0) return;
    emptyEl.innerHTML = "";
    var p = el("p");
    p.appendChild(document.createTextNode("No formula matches "));
    p.appendChild(el("strong")).textContent = "“" + query + "”";
    p.appendChild(document.createTextNode(". Try fewer or shorter words."));
    emptyEl.appendChild(p);
  }

  // ---------- 6. Copy LaTeX ----------
  function copyText(text, button) {
    function done(label) {
      button.textContent = label;
      setTimeout(function () { button.textContent = "TeX"; }, 1400);
    }
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      document.body.removeChild(ta);
      done(ok ? "Copied" : "Failed");
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done("Copied"); }, fallback);
    } else {
      fallback();
    }
  }

  // ---------- 7. Keyboard: "/" to search, Esc to clear ----------
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "/" && document.activeElement !== q) {
      ev.preventDefault();
      q.focus();
    } else if (ev.key === "Escape" && document.activeElement === q) {
      q.value = "";
      apply();
      q.blur();
    }
  });
  q.addEventListener("input", function () { apply(); window.scrollTo(0, 0); });

  // A link ending in #physics opens that tab; #statics opens that chapter.
  window.addEventListener("hashchange", function () {
    var place_ = findPlace(location.hash.slice(1));
    if (place_ && (place_.sheet !== current.sheet || place_.chapter !== current.chapter)) {
      select(place_.sheet, place_.chapter);
    }
  });

  // ---------- Info panel: the (i) button next to the title ----------
  var info = $("info");
  var installed = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
    window.navigator.standalone === true;      // opened from the Home Screen icon
  $("info-installed").hidden = !installed;
  $("info-install").hidden = installed;
  $("info-updated").textContent = "Last updated: " + (DATA.built || "").split(",")[0];
  $("info-btn").addEventListener("click", function () {
    if (info.showModal) info.showModal(); else info.setAttribute("open", "");
  });
  function closeInfo() { if (info.close) info.close(); else info.removeAttribute("open"); }
  $("info-close").addEventListener("click", closeInfo);
  info.addEventListener("click", function (ev) {   // tap outside the panel closes it
    if (ev.target === info) closeInfo();
  });

  // ---------- Theme: Auto (follows the device), Light or Dark ----------
  // The colours for both themes are in style.css; this only switches between
  // them and remembers the choice on this device.
  var themeButtons = document.querySelectorAll("[data-theme-choice]");
  var barColors = document.querySelectorAll('meta[name="theme-color"]');
  var BAR = { light: "#F3F5F1", dark: "#10151B" };   // colour of the phone's top bar
  function applyTheme(choice) {
    var root = document.documentElement;
    if (choice === "light" || choice === "dark") root.setAttribute("data-theme", choice);
    else root.removeAttribute("data-theme");
    for (var i = 0; i < barColors.length; i++) {
      var meta = barColors[i];
      if (!meta.getAttribute("data-auto")) meta.setAttribute("data-auto", meta.getAttribute("content"));
      meta.setAttribute("content", BAR[choice] || meta.getAttribute("data-auto"));
    }
    for (var j = 0; j < themeButtons.length; j++) {
      themeButtons[j].setAttribute("aria-pressed", String(themeButtons[j].getAttribute("data-theme-choice") === choice));
    }
  }
  var theme = "auto";
  try { theme = localStorage.getItem("formula-v2-theme") || "auto"; } catch (err) { /* storage blocked */ }
  applyTheme(theme);
  Array.prototype.forEach.call(themeButtons, function (button) {
    button.addEventListener("click", function () {
      theme = button.getAttribute("data-theme-choice");
      try {
        if (theme === "auto") localStorage.removeItem("formula-v2-theme"); else localStorage.setItem("formula-v2-theme", theme);
      } catch (err) { /* storage blocked: works until the page is closed */ }
      applyTheme(theme);
    });
  });

  // ---------- Owner mode: the TeX buttons only on your own devices ----------
  // Tap the title "Formula Finder V2" in the info panel 5 times quickly to turn
  // it on or off. It is remembered on this device only; others never see it.
  function setOwner(on) {
    document.documentElement.classList.toggle("owner", on);
    try {
      if (on) localStorage.setItem("formula-v2-owner", "1"); else localStorage.removeItem("formula-v2-owner");
    } catch (err) { /* storage blocked */ }
  }
  var ownerOn = false;
  try { ownerOn = localStorage.getItem("formula-v2-owner") === "1"; } catch (err) { /* storage blocked */ }
  setOwner(ownerOn);
  var taps = [];
  var ownerMsg = $("owner-msg");
  $("info-title").addEventListener("click", function () {
    var now = Date.now();
    taps = taps.filter(function (t) { return now - t < 2000; });   // taps in the last 2 seconds
    taps.push(now);
    if (taps.length < 5) return;
    taps = [];
    ownerOn = !ownerOn;
    setOwner(ownerOn);
    ownerMsg.textContent = ownerOn ? "Owner mode on: TeX buttons visible" : "Owner mode off";
    ownerMsg.hidden = false;
    clearTimeout(ownerMsg.timer);
    ownerMsg.timer = setTimeout(function () { ownerMsg.hidden = true; }, 2500);
  });

  // Keep the sticky header from covering a section you jump to.
  var topbar = $("topbar");
  function measure() {
    document.documentElement.style.setProperty("--head-h", topbar.offsetHeight + "px");
  }
  if (window.ResizeObserver) new ResizeObserver(measure).observe(topbar);
  measure();

  // ---------- 8. Offline app (service worker, see sw.js) ----------
  // Only in the installable version (web/index.html), which has a manifest.
  // sw.js keeps a copy of the app on your device so it opens without internet.
  // When you publish new formulas, the next time the app is opened online it
  // finds the new version and offers to reload.
  if ("serviceWorker" in navigator && document.querySelector('link[rel="manifest"]')) {
    // Show the "New formulas are available" bar if the saved copy of the app
    // differs from what is on screen (builder.py gives each build a "version").
    var checkForNewVersion = function () {
      if (!navigator.serviceWorker.controller) return;   // not installed yet
      fetch("index.html").then(function (r) { return r.text(); }).then(function (html) {
        if (html.indexOf('"version": "' + DATA.version + '"') === -1) $("update").hidden = false;   // a new app version
      }).catch(function () { /* offline: try again next time */ });
    };
    navigator.serviceWorker.register("sw.js").then(function (reg) {
      checkForNewVersion();
      // Phones keep apps open in the background: check again when you return.
      document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") reg.update().then(checkForNewVersion, function () {});
      });
    }).catch(function () { /* e.g. opened as a file: works, just not offline */ });
    navigator.serviceWorker.addEventListener("controllerchange", checkForNewVersion);
    $("reload").addEventListener("click", function () { location.reload(); });
  }

  footEl.innerHTML = "© 2026 Benjamin Bek. All rights reserved.<br>Formulas updated " + DATA.built + ".";
  apply();
};
