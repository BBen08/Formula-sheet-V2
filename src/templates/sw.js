/* sw.js - The "service worker": makes the app work offline.

   The browser runs this in the background. It keeps a copy of every file of
   the app on your device:
     - the page itself: always tries the internet first (so you get new
       formulas), and uses the saved copy when you are offline;
     - MathJax, icons, manifest: saved once, used from the device;
     - Google Fonts: used from the device, refreshed in the background.

   builder.py fills in VERSION (a fingerprint of all files) and FILES. When
   anything changes, VERSION changes, so the browser installs the new worker
   and the old saved copy is thrown away. */
var VERSION = "{{VERSION}}";
// V2 shares bben08.github.io with the original app, and both apps can see
// each other's saved copies. So V2 uses its own name and only ever deletes
// its own old copies. The font cache is shared on purpose: both apps use the
// same Google Fonts, and the original app never deletes that cache.
var PREFIX = "formula-finder-v2-";
var CACHE = PREFIX + VERSION;
var FONT_CACHE = "formula-finder-fonts";
var FILES = {{FILES}};
var NETWORK_TIMEOUT_MS = 3000;   // slow connection? use the saved copy after 3 s

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) {
        // cache: "reload" skips the browser's own short-term cache, so we
        // really save the new files and not a copy of the old ones.
        return cache.addAll(FILES.map(function (file) {
          return new Request(file, { cache: "reload" });
        }));
      })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (key) {
        // Only V2's own old copies: never touch the original app's caches.
        if (key.indexOf(PREFIX) === 0 && key !== CACHE) return caches.delete(key);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

function networkFirstPage(request) {
  return new Promise(function (resolve) {
    var done = false;
    function useCache() {
      if (done) return;
      caches.match("index.html", { cacheName: CACHE }).then(function (hit) {
        if (hit && !done) { done = true; resolve(hit); }
      });
    }
    var timer = setTimeout(useCache, NETWORK_TIMEOUT_MS);
    // "no-cache" asks the server whether the page changed (cheap if it did not).
    fetch(request.url, { cache: "no-cache", credentials: "same-origin" }).then(function (response) {
      clearTimeout(timer);
      if (response.ok) {
        var copy = response.clone();
        caches.open(CACHE).then(function (cache) { cache.put("index.html", copy); });
      }
      if (!done) { done = true; resolve(response); }
    }).catch(function () {
      clearTimeout(timer);
      useCache();
    });
  });
}

function staleWhileRevalidate(request) {
  return caches.open(FONT_CACHE).then(function (cache) {
    return cache.match(request).then(function (hit) {
      var fresh = fetch(request).then(function (response) {
        cache.put(request, response.clone());
        return response;
      }).catch(function () { return hit; });
      return hit || fresh;
    });
  });
}

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;
  var url = new URL(request.url);

  if (request.mode === "navigate") {
    event.respondWith(networkFirstPage(request));
  } else if (url.origin === self.location.origin) {
    // Look only in this version's own copy: while an update takes over, the
    // old copy still exists for a moment and must not be used.
    event.respondWith(caches.open(CACHE).then(function (cache) {
      return cache.match(request, { ignoreSearch: true });
    }).then(function (hit) {
      return hit || fetch(request);
    }));
  } else if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    event.respondWith(staleWhileRevalidate(request));
  }
});
