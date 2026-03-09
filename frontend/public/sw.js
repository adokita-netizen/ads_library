/**
 * VAAP ServiceWorker — Offline cache for static assets + API response caching.
 * Strategy: Network-first for API, Cache-first for static assets.
 */

const CACHE_NAME = "vaap-v1";
const STATIC_CACHE = "vaap-static-v1";
const API_CACHE = "vaap-api-v1";

// Static assets to pre-cache on install
const PRECACHE_URLS = ["/"];

// API paths eligible for caching (GET only)
const CACHEABLE_API_PATHS = [
  "/api/v1/rankings/genre-master",
  "/api/v1/rankings/search-collections",
];

// Cache TTL for API responses (5 minutes)
const API_CACHE_TTL = 5 * 60 * 1000;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== API_CACHE)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  const isHttp = url.protocol === "http:" || url.protocol === "https:";

  // Only cache GET requests
  if (request.method !== "GET") return;
  // Ignore unsupported schemes (e.g. chrome-extension://) to avoid Cache.put errors.
  if (!isHttp) return;

  // API caching — network-first with fallback
  if (url.pathname.startsWith("/api/v1/")) {
    const isCacheable = CACHEABLE_API_PATHS.some((p) =>
      url.pathname.startsWith(p)
    );

    if (isCacheable) {
      event.respondWith(networkFirstWithCache(request));
      return;
    }
    // Non-cacheable API — pass through
    return;
  }

  // Static assets — cache-first
  if (
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".woff2") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".ico")
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML navigation — network-first
  if (request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(networkFirst(request));
    return;
  }
});

async function networkFirstWithCache(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      const clone = response.clone();
      // Store with timestamp header
      const headers = new Headers(clone.headers);
      headers.set("sw-cached-at", String(Date.now()));
      const body = await clone.blob();
      const cachedResponse = new Response(body, {
        status: clone.status,
        statusText: clone.statusText,
        headers,
      });
      cache.put(request, cachedResponse);
    }
    return response;
  } catch {
    // Network failed — return cached if available and fresh
    const cached = await caches.match(request);
    if (cached) {
      const cachedAt = Number(cached.headers.get("sw-cached-at") || 0);
      if (Date.now() - cachedAt < API_CACHE_TTL) {
        return cached;
      }
    }
    return new Response(JSON.stringify({ error: "offline" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      try {
        await cache.put(request, response.clone());
      } catch {
        // Ignore non-cacheable responses.
      }
    }
    return response;
  } catch {
    return new Response("", { status: 503 });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      try {
        await cache.put(request, response.clone());
      } catch {
        // Ignore non-cacheable responses.
      }
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response("Offline", { status: 503 });
  }
}
