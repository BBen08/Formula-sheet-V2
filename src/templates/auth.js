/* auth.js - Login and downloading the formulas (V2 only).

   1. Not logged in?  Show the login screen: email -> Supabase sends a link.
   2. Clicked the link? Supabase puts the login in the address bar; supabase-js
      reads it and remembers it on this device (localStorage "formula-v2-auth").
   3. Logged in: download the cards. The database only gives them to users with
      free_access or a paid_until in the future (see supabase/schema.sql).
      No cards -> "No access yet" screen. Cards -> start the app (app.js) and
      save an offline copy (offline.js).
   4. No internet: show the offline copy (up to 15 days old, same user).

   window.FORMULA_APP (written by builder.py) holds the public project address
   and publishable key. They are meant to be public: the database rules decide
   who sees what. */
(function () {
  "use strict";

  var APP = window.FORMULA_APP;
  var OFF = window.FormulaOffline;   // offline.js
  var $ = function (id) { return document.getElementById(id); };
  var gate = $("gate");
  var started = false;

  var sb = window.supabase.createClient(APP.supabaseUrl, APP.supabaseKey, {
    auth: {
      // "implicit": the link in the email works in any browser, also when it
      // opens in a different browser than the one you typed your email in.
      flowType: "implicit",
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storageKey: "formula-v2-auth",   // V2's own name, separate from the original app
    },
  });

  // ---------- screens ----------
  function show(name, values) {
    var screens = gate.querySelectorAll("[data-screen]");
    for (var i = 0; i < screens.length; i++) {
      screens[i].hidden = screens[i].getAttribute("data-screen") !== name;
    }
    var fill = gate.querySelectorAll("[data-fill]");
    for (var j = 0; j < fill.length; j++) {
      var key = fill[j].getAttribute("data-fill");
      if (values && key in values) fill[j].textContent = values[key];
    }
    document.documentElement.classList.add("locked");
  }

  function unlock() {
    document.documentElement.classList.remove("locked");
    gate.hidden = true;
  }

  // ---------- login form ----------
  var form = $("login-form"), emailInput = $("login-email"), sendBtn = $("login-send"), msg = $("login-msg");

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var email = emailInput.value.trim();
    if (!email) return;
    sendBtn.disabled = true;
    msg.hidden = true;
    sb.auth.signInWithOtp({
      email: email,
      options: { emailRedirectTo: location.origin + location.pathname, shouldCreateUser: true },
    }).then(function (res) {
      sendBtn.disabled = false;
      if (res.error) {
        msg.textContent = res.error.status === 429
          ? "Too many emails were sent just now. Please wait a few minutes and try again."
          : "Could not send the email: " + res.error.message;
        msg.hidden = false;
        return;
      }
      show("sent", { email: email });
    }, function () {
      sendBtn.disabled = false;
      msg.textContent = "No connection. Check your internet and try again.";
      msg.hidden = false;
    });
  });

  $("login-other").addEventListener("click", function () { show("login"); emailInput.focus(); });

  // Log out: delete the offline copy first, then the login itself. The login is
  // also removed from this device by hand, in case there is no internet.
  function logOut() {
    function done() {
      try { localStorage.removeItem("formula-v2-auth"); } catch (err) { /* ignore */ }
      location.replace(location.pathname);
    }
    OFF.remove().then(function () { return sb.auth.signOut({ scope: "local" }); }).then(done, done);
  }
  var logoutButtons = document.querySelectorAll("[data-logout]");
  for (var i = 0; i < logoutButtons.length; i++) logoutButtons[i].addEventListener("click", logOut);

  var retryButtons = document.querySelectorAll("[data-retry]");
  for (var k = 0; k < retryButtons.length; k++) {
    retryButtons[k].addEventListener("click", function () { location.reload(); });
  }

  // ---------- after login ----------
  function load(session) {
    if (started) return;
    started = true;
    var email = (session.user && session.user.email) || "";
    $("info-account").textContent = email;
    show("loading");
    // Remove the login details from the address bar (they are saved already).
    if (/access_token|error_description/.test(location.hash)) {
      try { history.replaceState(null, "", location.pathname); } catch (err) { /* ignore */ }
    }
    sb.rpc("touch_last_seen").then(function () {}, function () {});   // "last seen" for you, the owner

    var userId = session.user.id;
    sb.from("cards").select("*").order("position").range(0, 4999).then(function (res) {
      if (res.error) {
        started = false;
        // status 0 = no answer at all, so no internet: use the offline copy.
        return res.status === 0 || navigator.onLine === false ? useOfflineCopy(userId) : show("error");
      }
      if (!res.data.length) {               // no (longer) access: also no offline copy
        OFF.remove();
        return noAccess(email);
      }
      var data = toData(res.data);
      OFF.save(userId, data);
      start(data, null);
    }, function () { started = false; useOfflineCopy(userId); });
  }

  function start(data, offlineSince) {
    started = true;
    unlock();
    window.startFormulaApp(data);
    typeset();
    var note = $("offline-note");
    if (offlineSince) {
      note.textContent = "Offline: formulas from " + new Date(offlineSince).toLocaleDateString("en-GB",
        { day: "numeric", month: "short" }) + ". Works offline for up to " + OFF.OFFLINE_DAYS + " days.";
      note.hidden = false;
    }
  }

  // No internet: show the saved copy if it belongs to this user and is recent.
  function useOfflineCopy(userId) {
    return OFF.load().then(function (copy) {
      var decision = OFF.decide(copy, userId, Date.now());
      if (decision === "show") start(copy.data, copy.savedAt);
      else show(decision === "too-old" ? "offline-old" : "error", { days: String(OFF.OFFLINE_DAYS) });
    });
  }

  // Who was logged in on this device (also readable without internet).
  function savedUserId() {
    try {
      var saved = JSON.parse(localStorage.getItem("formula-v2-auth") || "null");
      return saved && saved.user && saved.user.id;
    } catch (err) { return null; }
  }

  // true if Supabase answers at all (any answer means we are online).
  function online() {
    return fetch(APP.supabaseUrl + "/auth/v1/health", { headers: { apikey: APP.supabaseKey } })
      .then(function () { return true; }, function () { return false; });
  }

  // Not logged in according to Supabase. Without internet that can also mean
  // "the login could not be renewed", so use the offline copy in that case.
  function notLoggedIn() {
    var userId = savedUserId();
    if (!userId) return show("login");
    online().then(function (isOnline) {
      if (isOnline) { OFF.remove(); show("login"); }
      else useOfflineCopy(userId);
    });
  }

  // Logged in, but the database gave no cards: tell the user why.
  function noAccess(email) {
    sb.from("profiles").select("paid_until").maybeSingle().then(function (res) {
      var paid = res.data && res.data.paid_until;
      show(paid && new Date(paid) < new Date() ? "expired" : "noaccess", { email: email });
    }, function () { show("noaccess", { email: email }); });
  }

  // Rows from the database -> the same shape builder.py used to write into
  // the page, so app.js works unchanged: sheets > chapters + sections > cards.
  function toData(rows) {
    var sheets = [], sheetById = {}, chapterSeen = {}, sectionById = {}, latest = "";
    rows.forEach(function (r) {
      var sheet = sheetById[r.tab];
      if (!sheet) {
        sheet = sheetById[r.tab] = { id: r.tab, name: r.tab_name, title: r.tab_title || "", chapters: [], sections: [] };
        sheets.push(sheet);
      }
      if (!chapterSeen[r.chapter]) {
        chapterSeen[r.chapter] = true;
        sheet.chapters.push({ id: r.chapter, name: r.chapter_name, source: r.chapter_source || "" });
      }
      var section = sectionById[r.section];
      if (!section) {
        section = sectionById[r.section] = {
          id: r.section, title_html: r.section_title_html, title_text: r.section_title_text,
          color: r.section_color, intro_html: r.section_intro_html || "", chapter: r.chapter, cards: [],
        };
        sheet.sections.push(section);
      }
      section.cards.push({
        id: r.id, title_html: r.title_html, title_text: r.title_text,
        body_html: r.body_html, body_text: r.body_text, latex: r.latex,
      });
      if (r.uploaded_at > latest) latest = r.uploaded_at;
    });
    var d = latest ? new Date(latest) : null;
    return {
      version: APP.version,
      built: d ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) +
        ", " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "",
      sheets: sheets,
    };
  }

  // MathJax loads in the background; draw the maths once both are ready.
  function typeset() {
    if (window.MathJax && window.MathJax.typesetPromise) window.MathJax.typesetPromise();
    else window.typesetWhenReady = true;
  }

  // An old or already used link comes back with an error in the address bar.
  if (/error_description/.test(location.hash)) {
    msg.textContent = "That login link has expired or was already used. Send yourself a new one.";
    msg.hidden = false;
    try { history.replaceState(null, "", location.pathname); } catch (err) { /* ignore */ }
  }

  // ---------- start ----------
  // Fires once at start (INITIAL_SESSION) and again after logging in or out.
  // Supabase asks not to call it from inside this callback, hence setTimeout.
  sb.auth.onAuthStateChange(function (event, session) {
    setTimeout(function () {
      if (session) load(session);
      else if (event === "INITIAL_SESSION") notLoggedIn();
      else if (event === "SIGNED_OUT" && !started) { OFF.remove(); show("login"); }
    }, 0);
  });
})();
