/**
 * Simple in-memory request cache for prefetching API data.
 * Stores promises (not resolved values) to deduplicate concurrent requests.
 */

import { fetchApi } from "./api";

interface CacheEntry<T = unknown> {
  promise: Promise<T>;
  timestamp: number;
}

const cache = new Map<string, CacheEntry>();
const DEFAULT_TTL = 60_000; // 60 seconds

function cacheKey(
  path: string,
  params?: Record<string, string | number | undefined>,
): string {
  const base = path;
  if (!params) return base;
  const sorted = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join("&");
  return sorted ? `${base}?${sorted}` : base;
}

/**
 * Fire-and-forget prefetch. Stores the promise in cache so subsequent
 * calls to `cachedFetchApi` with the same path/params return instantly.
 */
export function prefetchApi<T = unknown>(
  path: string,
  params?: Record<string, string | number | undefined>,
): void {
  const key = cacheKey(path, params);
  const existing = cache.get(key);
  if (existing && Date.now() - existing.timestamp < DEFAULT_TTL) return;

  const promise = fetchApi<T>(path, { params });
  cache.set(key, { promise, timestamp: Date.now() });

  // Clean up on failure so the next request retries
  promise.catch(() => {
    const entry = cache.get(key);
    if (entry && entry.promise === promise) cache.delete(key);
  });
}

/**
 * Returns cached data if available and fresh, otherwise fetches and caches.
 */
export async function cachedFetchApi<T = unknown>(
  path: string,
  options?: {
    params?: Record<string, string | number | undefined>;
    ttl?: number;
  },
): Promise<T> {
  const key = cacheKey(path, options?.params);
  const ttl = options?.ttl ?? DEFAULT_TTL;

  const existing = cache.get(key);
  if (existing && Date.now() - existing.timestamp < ttl) {
    return existing.promise as Promise<T>;
  }

  const promise = fetchApi<T>(path, { params: options?.params });
  cache.set(key, { promise, timestamp: Date.now() });

  promise.catch(() => {
    const entry = cache.get(key);
    if (entry && entry.promise === promise) cache.delete(key);
  });

  return promise;
}

/**
 * Invalidate a specific cache entry.
 */
export function invalidateCache(
  path: string,
  params?: Record<string, string | number | undefined>,
): void {
  cache.delete(cacheKey(path, params));
}
