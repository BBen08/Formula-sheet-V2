/* offline.js - The offline copy of the formulas (V2 only).

   Each time the formulas are downloaded (online, with access), a copy is saved
   on this device in IndexedDB, the browser's own small database. The original
   Formula Finder never touches it, also not when it updates.

   Rules:
     - offline, logged in as the same user, copy younger than OFFLINE_DAYS:
       show the copy;
     - copy older than OFFLINE_DAYS: go online once first;
     - log out, or online without access: the copy is deleted at once. */
window.FormulaOffline = (function () {
  "use strict";

  var OFFLINE_DAYS = 15;
  var DAY_MS = 24 * 60 * 60 * 1000;
  var DB_NAME = "formula-finder-v2", STORE = "offline", KEY = "copy";

  // What to do with a saved copy. Returns "show", "too-old" or "none".
  function decide(copy, userId, now) {
    if (!copy || !copy.data || !userId || copy.userId !== userId) return "none";
    var age = now - copy.savedAt;
    if (!(age >= 0)) return "none";                 // clock was changed: do not trust it
    return age <= OFFLINE_DAYS * DAY_MS ? "show" : "too-old";
  }

  function open() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) return reject(new Error("no IndexedDB"));
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () { req.result.createObjectStore(STORE); };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function run(mode, action) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, mode);
        var req = action(tx.objectStore(STORE));
        tx.oncomplete = function () { db.close(); resolve(req && req.result); };
        tx.onerror = tx.onabort = function () { db.close(); reject(tx.error); };
      });
    });
  }

  function save(userId, data) {
    return run("readwrite", function (store) {
      return store.put({ userId: userId, savedAt: Date.now(), data: data }, KEY);
    }).catch(function () { /* storage full or blocked: just no offline copy */ });
  }

  function load() {
    return run("readonly", function (store) { return store.get(KEY); })
      .catch(function () { return null; });
  }

  function remove() {
    return run("readwrite", function (store) { return store.delete(KEY); })
      .catch(function () { /* nothing saved */ });
  }

  return { OFFLINE_DAYS: OFFLINE_DAYS, decide: decide, save: save, load: load, remove: remove };
})();
