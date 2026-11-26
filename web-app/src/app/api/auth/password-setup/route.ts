import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

export function POST(request: NextRequest) {
  return proxyBackend(request, '/api/auth/password-setup', false);
}
