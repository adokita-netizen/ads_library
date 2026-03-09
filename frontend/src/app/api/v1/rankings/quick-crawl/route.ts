import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function resolveBackendBaseUrl(): string {
  if (process.env.BACKEND_URL) return process.env.BACKEND_URL;
  if (process.env.NODE_ENV !== "production") return "http://127.0.0.1:8000";
  return "http://127.0.0.1:8000";
}

export async function POST(req: NextRequest) {
  const backendBase = resolveBackendBaseUrl();
  const targetUrl = `${backendBase}/api/v1/rankings/quick-crawl`;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: { code: "bad_request", message: "Invalid JSON body" } },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 240_000);

  try {
    const res = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });

    const text = await res.text();
    const contentType = res.headers.get("content-type") || "application/json";
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (err) {
    const isAbort = err instanceof Error && err.name === "AbortError";
    const status = isAbort ? 504 : 502;
    const message = isAbort ? "Quick crawl proxy timeout" : "Quick crawl proxy failed";
    return NextResponse.json(
      { error: { code: "proxy_error", message } },
      { status },
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

