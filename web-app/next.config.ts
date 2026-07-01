import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Enable standalone output for optimised Docker images
  output: 'standalone',

  // Transpile Three.js ecosystem packages (required for App Router / RSC)
  transpilePackages: ['three', '@react-three/fiber', '@react-three/drei'],
};

export default nextConfig;
