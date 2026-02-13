/**
 * Health check endpoint for the Next.js server.
 * Tests connectivity to the FastAPI backend and returns diagnostics.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET() {
  const diagnostics: Record<string, unknown> = {
    nextjs: "ok",
    timestamp: new Date().toISOString(),
    backend_url: BACKEND_URL,
    env_api_url: process.env.NEXT_PUBLIC_API_URL || "(not set, using default)",
  };

  // Test backend connectivity
  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    const data = await res.json();
    diagnostics.backend = "ok";
    diagnostics.backend_response = data;
  } catch (err) {
    diagnostics.backend = "error";
    diagnostics.backend_error = String(err);
  }

  return new Response(JSON.stringify(diagnostics, null, 2), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
