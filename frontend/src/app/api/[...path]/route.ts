/**
 * Catch-all API proxy route.
 * Forwards all /api/* requests to the FastAPI backend.
 * This is the primary API proxy — more reliable than next.config.js rewrites.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxyRequest(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const targetUrl = `${BACKEND_URL}${url.pathname}${url.search}`;

  try {
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
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      const body = await request.text();
      if (body) fetchOptions.body = body;
    }

    const backendResponse = await fetch(targetUrl, fetchOptions);
    const responseBody = await backendResponse.text();

    return new Response(responseBody, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: {
        "content-type": backendResponse.headers.get("content-type") || "application/json",
        "cache-control": "no-cache, no-store, must-revalidate",
      },
    });
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error);
    console.error(`[API Proxy] ${request.method} ${url.pathname} -> ${targetUrl} FAILED:`, errMsg);
    return Response.json(
      {
        error: {
          code: "proxy_error",
          message: "バックエンドサーバーに接続できません",
          detail: errMsg,
          target: targetUrl,
        },
      },
      { status: 502 }
    );
  }
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
