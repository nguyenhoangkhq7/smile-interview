import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

type Context = { params: Promise<{ path?: string[] }> };
const base = '/api/v1/admin/interview-sessions';

export async function GET(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  if (!path.length) return proxyBackend(request, base);
  if (path.length === 1 && path[0] === 'detail') return proxyBackend(request, base + '/detail');
  return Response.json({ message: 'Not found' }, { status: 404 });
}
