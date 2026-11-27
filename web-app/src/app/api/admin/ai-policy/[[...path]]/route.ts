import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

type Context = { params: Promise<{ path?: string[] }> };
const base = '/api/v1/admin/ai-policy';

function notFound() {
  return Response.json({ message: 'Not found' }, { status: 404 });
}

export async function GET(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  if (!path.length) return proxyBackend(request, base);
  if (path.length === 1 && path[0] === 'health') return proxyBackend(request, base + '/health');
  return notFound();
}

export async function PUT(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  return path.length ? notFound() : proxyBackend(request, base);
}

export async function POST(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  if (path.length === 1 && path[0] === 'reset') return proxyBackend(request, base + '/reset');
  if (path.length === 1 && path[0] === 'health') return proxyBackend(request, base + '/health');
  return notFound();
}
