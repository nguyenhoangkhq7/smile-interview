import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

type Context = { params: Promise<{ path?: string[] }> };
const base = '/api/v1/admin/audit-logs';

export async function GET(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  if (!path.length) return proxyBackend(request, base);
  if (path.length === 1 && (path[0] === 'export' || /^[1-9][0-9]{0,18}$/.test(path[0]))) {
    return proxyBackend(request, base + '/' + path[0]);
  }
  return Response.json({ message: 'Not found' }, { status: 404 });
}
