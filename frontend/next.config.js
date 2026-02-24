/** @type {import('next').NextConfig} */
const isStaticExport = process.env.NEXT_OUTPUT === "export";

const nextConfig = {
  // Static export for S3+CloudFront deployment (set NEXT_OUTPUT=export)
  ...(isStaticExport
    ? { output: "export", images: { unoptimized: true } }
    : {}),
  // API proxy is handled by /src/app/api/[...path]/route.ts (dev/Vercel only)
};

module.exports = nextConfig;
