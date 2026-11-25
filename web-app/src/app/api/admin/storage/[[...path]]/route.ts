import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

type Context = { params: Promise<{ path?: string[] }> };

export async function GET(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  if (!path.length) return proxyBackend(request, '/api/v1/admin/storage');
  return Response.json({ message: 'Not found' }, { status: 404 });
}

export async function POST(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  if (path.length === 1 && path[0] === 'cleanup') return proxyBackend(request, '/api/v1/admin/storage/cleanup');
  return Response.json({ message: 'Not found' }, { status: 404 });
}
