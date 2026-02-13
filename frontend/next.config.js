/** @type {import('next').NextConfig} */
const nextConfig = {
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
