import type { NextConfig } from "next";
import { resolve } from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // v39.3.0: Fix Turbopack "couldn't find Next.js package" on Windows.
  // When running from non-standard paths (e.g., Downloads folder),
  // Turbopack fails to resolve the workspace root. Setting turbopack.root
  // to an absolute path ensures correct resolution on any OS.
  turbopack: { root: resolve(".") },
  allowedDevOrigins: [
    "https://*.space-z.ai",
    "https://*.space.z.ai",
  ],
  async headers() {
    return [{
      source: '/(.*)',
      headers: [
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'X-XSS-Protection', value: '1; mode=block' },
      ],
    }]
  },
};

export default nextConfig;
