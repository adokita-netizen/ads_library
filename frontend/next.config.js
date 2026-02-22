/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export for S3+CloudFront deployment (set NEXT_OUTPUT=export)
  ...(process.env.NEXT_OUTPUT === "export"
    ? { output: "export", images: { unoptimized: true } }
    : {}),
  // API proxy is handled by /src/app/api/[...path]/route.ts
  // No rewrites needed — route handlers are more reliable in dev mode
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
