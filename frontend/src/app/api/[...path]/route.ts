/**
 * Catch-all API proxy route.
 * Forwards all /api/* requests to the FastAPI backend.
 * More reliable than next.config.js rewrites (works without restart).
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxyRequest(request: Request): Promise<Response> {
  const url = new URL(request.url);
  // Forward the full /api/... path to the backend
  const targetUrl = `${BACKEND_URL}${url.pathname}${url.search}`;

  try {
    const headers = new Headers();
    // Forward relevant headers
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    const auth = request.headers.get("authorization");
    if (auth) headers.set("authorization", auth);
    headers.set("accept", "application/json");

    const fetchOptions: RequestInit = {
      method: request.method,
      headers,
    };

    // Forward body for non-GET requests
    if (request.method !== "GET" && request.method !== "HEAD") {
      const body = await request.text();
      if (body) fetchOptions.body = body;
    }

    const backendResponse = await fetch(targetUrl, fetchOptions);

    // Forward the response back
    const responseBody = await backendResponse.text();
    return new Response(responseBody, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: {
        "content-type": backendResponse.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    console.error("[API Proxy] Backend connection error:", error);
    return new Response(
      JSON.stringify({
        error: {
          code: "proxy_error",
          message: "バックエンドサーバーに接続できません",
          detail: `Backend URL: ${BACKEND_URL}, Path: ${url.pathname}`,
        },
      }),
      {
        status: 502,
        headers: { "content-type": "application/json" },
      }
    );
  }
}

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
