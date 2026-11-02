/* JARVIS HUD service worker (Task 7.9). App-shell caching only —
// live state always comes from the /events WebSocket, never from cache. */
var CACHE = "jarvis-hud-v1";
var SHELL = [
  "/hud/index.html",
  "/hud/styles.css",
  "/hud/app.js",
  "/hud/manifest.json"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  // Never cache API or event streams — always go to the network.
  if (url.pathname === "/events" || url.pathname === "/command" ||
      url.pathname === "/hud/snapshot" || url.pathname.indexOf("/api/") === 0) {
    return;
  }
  e.respondWith(
    caches.match(e.request).then(function (hit) { return hit || fetch(e.request); })
  );
});
