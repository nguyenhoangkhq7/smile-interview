import type { NextRequest } from 'next/server';

export async function proxyBackend(request: NextRequest, path: string, requireAuth = true) {
  const headers = new Headers({ 'Cache-Control': 'no-store' });
  const authorization = request.headers.get('authorization');
  if (requireAuth && !authorization) {
    return Response.json({ message: 'Authentication required' }, { status: 401, headers });
  }

  try {
    const baseUrl = process.env.BACKEND_INTERNAL_URL
      || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8081';
    const target = new URL(path, baseUrl);
    target.search = request.nextUrl.search;
    const outgoing = new Headers();
    if (requireAuth && authorization) outgoing.set('Authorization', authorization);
    const contentType = request.headers.get('content-type');
    if (contentType) outgoing.set('Content-Type', contentType);

    const response = await fetch(target, {
      method: request.method,
      headers: outgoing,
      body: request.method === 'GET' ? undefined : await request.text() || undefined,
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(30_000)]),
    });
    for (const name of ['Content-Type', 'Content-Disposition']) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers });
  } catch (error) {
    if (!request.signal.aborted) console.error('Backend request failed', error);
    return Response.json({ message: 'Backend unavailable' }, { status: 502, headers });
  }
}
