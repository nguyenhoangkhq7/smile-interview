import type { NextRequest } from 'next/server';
import { proxyBackend } from '@/lib/server/proxyBackend';

type Context = { params: Promise<{ path?: string[] }> };

const users = '/api/v1/admin/users';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function forward(request: NextRequest, { params }: Context) {
  const { path = [] } = await params;
  const [id, action] = path;
  const method = request.method;

  if (path.length === 0 && (method === 'GET' || method === 'POST')) {
    return proxyBackend(request, users);
  }
  if (path.length === 1 && method === 'GET' && (id === 'export' || uuid.test(id))) {
    return proxyBackend(request, users + '/' + id);
  }
  if (path.length === 2 && uuid.test(id) && (
    (method === 'PATCH' && action === 'status')
    || (method === 'POST' && action === 'password-setup')
  )) {
    return proxyBackend(request, users + '/' + id + '/' + action);
  }
  return Response.json({ message: 'Not found' }, { status: 404 });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
