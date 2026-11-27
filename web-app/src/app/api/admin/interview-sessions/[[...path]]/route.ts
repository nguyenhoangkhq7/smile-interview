import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

type Context = { params: Promise<{ path?: string[] }> };
const base = '/api/v1/admin/interview-sessions';
const resources = new Set(['detail', 'quality', 'matching', 'document', 'document-file']);

export async function GET(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  if (!path.length) return proxyBackend(request, base);
  if (path.length === 1 && resources.has(path[0])) return proxyBackend(request, base + '/' + path[0]);
  return Response.json({ message: 'Not found' }, { status: 404 });
}
