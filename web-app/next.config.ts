import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Enable standalone output for optimised Docker images
  output: 'standalone',

  // Test-only SDK stand-in. Production always resolves the real Simli package.
  ...(process.env.NODE_ENV === 'development' && process.env.SIMLI_TEST_DRIVER === '1'
    ? { turbopack: { resolveAlias: { 'simli-client': './scripts/fixtures/simli-client.ts' } } }
    : {}),
};

export default nextConfig;
