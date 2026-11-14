// Fa funzionare l'app anche senza connessione. I file dell'app si aggiornano da soli quando c'è rete.
var CACHE = "stipendio-pilota-v49";
var SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png", "./icons/icon-512.png", "./icons/apple-touch-icon.png"];
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  var same = new URL(e.request.url).origin === self.location.origin;
  if (same) {
    // File dell'app: prima la rete (così vedi sempre l'ultima versione), poi la copia salvata.
    e.respondWith(fetch(e.request).then(function (r) {
      if (r && r.status === 200) { var copy = r.clone(); caches.open(CACHE).then(function (c) { c.put(e.request, copy); }); }
      return r;
    }).catch(function () { return caches.match(e.request).then(function (h) { return h || caches.match("./index.html"); }); }));
  } else {
    // Font e altro: prima la copia salvata.
    e.respondWith(caches.match(e.request).then(function (hit) {
      return hit || fetch(e.request).then(function (r) {
        if (r && (r.status === 200 || r.type === "opaque")) { var copy = r.clone(); caches.open(CACHE).then(function (c) { c.put(e.request, copy); }); }
        return r;
      });
    }));
  }
});
self.addEventListener("push", function (e) {
  var d = {}; try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "Stipendio Pilota", { body: d.body || "Oggi è il giorno della paga.", icon: "./icons/icon-192.png", badge: "./icons/icon-192.png", tag: "stipendio", data: { url: d.url || "./#home" } }));
});
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || "./#home";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) { if ("focus" in list[i]) { list[i].navigate && list[i].navigate(url); return list[i].focus(); } }
    return self.clients.openWindow(url);
  }));
});
