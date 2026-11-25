import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

export function GET(request: NextRequest) {
  return proxyBackend(request, '/api/v1/admin/overview');
}
