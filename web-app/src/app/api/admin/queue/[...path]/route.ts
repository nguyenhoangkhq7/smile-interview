import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

type Context = { params: Promise<{ path: string[] }> };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function forward(request: NextRequest, { params }: Context) {
  const { path } = await params;
  const [collection, id, action] = path;
  const method = request.method;
  if (collection === 'jobs' && (
    (method === 'GET' && (path.length === 1 || (path.length === 2 && uuid.test(id))))
    || (method === 'POST' && path.length === 3 && uuid.test(id) && ['prioritize', 'release'].includes(action))
  )) {
    return proxyBackend(request, '/api/v1/admin/queue/' + path.join('/'));
  }
  return Response.json({ message: 'Not found' }, { status: 404 });
}

export const GET = forward;
export const POST = forward;
