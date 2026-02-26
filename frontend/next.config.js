/** @type {import('next').NextConfig} */
const isStaticExport = process.env.NEXT_OUTPUT === "export";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  // Static export for S3+CloudFront deployment (set NEXT_OUTPUT=export)
  ...(isStaticExport
    ? { output: "export", images: { unoptimized: true } }
    : {
        // Proxy /api requests to FastAPI backend during local development
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
