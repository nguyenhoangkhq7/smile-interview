import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Enable standalone output for optimised Docker images
  output: 'standalone',
  images: {
    remotePatterns: [{ protocol: 'https', hostname: 'images.unsplash.com' }],
  },

  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
        ],
      },
    ];
  },

  // Test-only SDK stand-in. Production always resolves the real Simli package.
  ...(process.env.NODE_ENV === 'development' && process.env.SIMLI_TEST_DRIVER === '1'
    ? { turbopack: { resolveAlias: { 'simli-client': './scripts/fixtures/simli-client.ts' } } }
    : {}),
};

export default nextConfig;
