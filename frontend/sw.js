/**
 * KisanSetu — Offline-Resilient Rural Service Worker
 * Ensures digital gate passes, signed tokens, and UI scaffolding
 * remain fully interactive without internet access.
 */

const CACHE_NAME = "kisan-setu-v1";
const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/farmer/dashboard.html",
  "/farmer/token.html",
  "/farmer/booking.html",
  "/farmer/queue.html",
  "/css/style.css",
  "/js/utils.js",
  "/js/auth.js",
  "/js/api.js",
  "/js/throughput-engine.js",
  "/js/state-machine.js",
  "/js/qr-security.js",
  "/js/offline-storage.js",
  "/js/i18n.js",
  "/js/event-bus.js",
  "/assets/logo.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn("ServiceWorker caching failed partially:", err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Pass WebSocket or POST requests straight through
  if (event.request.method !== "GET" || event.request.url.includes("/api/v1/ws/")) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      // Return cached asset if found, otherwise network
      const networkFetch = fetch(event.request).then((response) => {
        if (response && response.status === 200 && response.type === "basic") {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
        }
        return response;
      }).catch(() => {
        // Fallback for HTML documents when completely offline
        if (event.request.headers.get("accept") && event.request.headers.get("accept").includes("text/html")) {
          return caches.match("/farmer/token.html");
        }
      });

      return cached || networkFetch;
    })
  );
});
