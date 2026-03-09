/** @type {import('next').NextConfig} */
const isStaticExport = process.env.NEXT_OUTPUT === "export";
const isDev = process.env.NODE_ENV !== "production";

// Prevent accidental remote proxy targets during local development.
// In dev, force local FastAPI unless ALLOW_REMOTE_BACKEND=1 is set.
const BACKEND_URL = isDev && process.env.ALLOW_REMOTE_BACKEND !== "1"
  ? "http://127.0.0.1:8000"
  : (process.env.BACKEND_URL || "http://127.0.0.1:8000");

const nextConfig = {
  ...(isStaticExport
    ? { output: "export", images: { unoptimized: true } }
    : {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `${BACKEND_URL}/api/:path*`,
            },
            {
              source: "/health",
              destination: `${BACKEND_URL}/health`,
            },
          ];
        },
      }),
};

module.exports = nextConfig;
