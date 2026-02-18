/**
 * Catch-all API proxy route.
 * Forwards all /api/* requests to the FastAPI backend.
 * This is the primary API proxy — more reliable than next.config.js rewrites.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PROXY_TIMEOUT_MS = 55_000; // 55 second timeout (Vercel max is 60s)
const MAX_RETRIES = 1; // Retry once on connection errors (handles Render cold starts)
const RETRY_DELAY_MS = 2_000;

async function fetchWithRetry(
  targetUrl: string,
  fetchOptions: RequestInit,
  method: string,
  pathname: string,
): Promise<{ response?: globalThis.Response; error?: string; isTimeout?: boolean }> {
  let lastError = "";

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(targetUrl, fetchOptions);
      // Retry on 502/503 from backend (Render waking up)
      if ((response.status === 502 || response.status === 503) && attempt < MAX_RETRIES) {
        console.log(
          `[API Proxy] ${method} ${pathname} -> ${response.status}, retrying in ${RETRY_DELAY_MS}ms (attempt ${attempt + 1})`
        );
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
        continue;
      }
      return { response };
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      const isTimeout = lastError.includes("timeout") || lastError.includes("abort");

      // Don't retry on timeout (already used up our time budget)
      if (isTimeout || attempt >= MAX_RETRIES) {
        return { error: lastError, isTimeout };
      }

      console.log(
        `[API Proxy] ${method} ${pathname} -> connection error, retrying in ${RETRY_DELAY_MS}ms (attempt ${attempt + 1})`
      );
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
    }
  }

  return { error: lastError, isTimeout: false };
}

async function proxyRequest(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const targetUrl = `${BACKEND_URL}${url.pathname}${url.search}`;
  const startMs = Date.now();

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const auth = request.headers.get("authorization");
  if (auth) headers.set("authorization", auth);
  headers.set("accept", "application/json");

  const fetchOptions: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(PROXY_TIMEOUT_MS),
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.text();
    if (body) fetchOptions.body = body;
  }

  const result = await fetchWithRetry(targetUrl, fetchOptions, request.method, url.pathname);

  if (result.response) {
    const backendResponse = result.response;
    const responseBody = await backendResponse.text();
    const elapsed = Date.now() - startMs;

    console.log(
      `[API Proxy] ${request.method} ${url.pathname} -> ${backendResponse.status} (${elapsed}ms, ${responseBody.length}b)`
    );

    // Forward cache-control from backend if present, otherwise default
    const backendCacheControl = backendResponse.headers.get("cache-control");

    return new Response(responseBody, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: {
        "content-type": backendResponse.headers.get("content-type") || "application/json",
        "cache-control": backendCacheControl || "no-cache, no-store, must-revalidate",
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
        "access-control-allow-headers": "content-type, authorization",
      },
    });
  }

  // Error case
  const elapsed = Date.now() - startMs;
  console.error(
    `[API Proxy] ${request.method} ${url.pathname} -> FAILED (${elapsed}ms): ${result.error}`
  );
  return Response.json(
    {
      error: {
        code: result.isTimeout ? "proxy_timeout" : "proxy_error",
        message: result.isTimeout
          ? "バックエンドサーバーの応答がタイムアウトしました"
          : "バックエンドサーバーに接続できません",
        detail: result.error,
        target: targetUrl,
        elapsed_ms: elapsed,
      },
    },
    {
      status: result.isTimeout ? 504 : 502,
      headers: {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
      },
    }
  );
}

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return proxyRequest(request);
}

export async function POST(request: Request) {
  return proxyRequest(request);
}

export async function PUT(request: Request) {
  return proxyRequest(request);
}

export async function DELETE(request: Request) {
  return proxyRequest(request);
}

export async function PATCH(request: Request) {
  return proxyRequest(request);
}

export async function OPTIONS() {
  return new Response(null, {
    status: 204,
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
      "access-control-allow-headers": "content-type, authorization",
    },
  });
}
