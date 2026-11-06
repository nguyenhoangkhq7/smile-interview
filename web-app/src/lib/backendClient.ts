import { customFetch } from './customFetch';

export const BACKEND_BASE_URL = process.env.MATCHING_SERVICE_URL || 'http://localhost:8081';

/**
 * Clean helper to forward requests from Next.js BFF routes to the Spring Boot backend.
 * Automatically forwards Authorization headers and handles timeout.
 */
export async function forwardToBackend(
  endpoint: string,
  request?: Request,
  init?: RequestInit
): Promise<Response> {
  const url = `${BACKEND_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(init?.headers);

  if (request) {
    const authHeader = request.headers.get('Authorization');
    if (authHeader && !headers.has('Authorization')) {
      headers.set('Authorization', authHeader);
    }
  }

  return customFetch(url, {
    ...init,
    headers,
  });
}
