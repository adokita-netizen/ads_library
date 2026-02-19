/**
 * Health check endpoint for the Next.js server.
 * Tests connectivity to the FastAPI backend with cold-start retry.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WARMUP_TIMEOUT_MS = 10_000;
const WARMUP_RETRIES = 5;
const WARMUP_DELAY_MS = 3_000;

async function pingBackend(): Promise<{ ok: boolean; data?: Record<string, unknown>; error?: string }> {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      signal: AbortSignal.timeout(WARMUP_TIMEOUT_MS),
      cache: "no-store",
    });
    const data = await res.json();
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

export async function GET() {
  const diagnostics: Record<string, unknown> = {
    nextjs: "ok",
    timestamp: new Date().toISOString(),
    backend_url: BACKEND_URL,
    env_api_url: process.env.NEXT_PUBLIC_API_URL || "(not set, using default)",
  };

  // Retry with backoff to handle Render free-tier cold starts (up to ~50s)
  let lastError = "";
  for (let attempt = 0; attempt < WARMUP_RETRIES; attempt++) {
    const result = await pingBackend();
    if (result.ok) {
      diagnostics.backend = "ok";
      diagnostics.backend_response = result.data;
      diagnostics.warmup_attempts = attempt + 1;
      return new Response(JSON.stringify(diagnostics, null, 2), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    lastError = result.error || "unknown";
    if (attempt < WARMUP_RETRIES - 1) {
      await new Promise((r) => setTimeout(r, WARMUP_DELAY_MS));
    }
  }

  diagnostics.backend = "error";
  diagnostics.backend_error = lastError;
  diagnostics.warmup_attempts = WARMUP_RETRIES;

  return new Response(JSON.stringify(diagnostics, null, 2), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
