import { Agent } from 'undici';

// Create custom Undici agent with 5-minute timeout for headers and body
const customAgent = new Agent({
  headersTimeout: 300_000, // 5 minutes (300,000 ms)
  bodyTimeout: 300_000,    // 5 minutes (300,000 ms)
  connectTimeout: 60_000,   // 1 minute (60,000 ms)
});

/**
 * Custom fetch wrapper for server-side API proxy routes to prevent UND_ERR_HEADERS_TIMEOUT
 * when backend operations (e.g. LLM assessment) take longer than Node's 30s default limit.
 */
export async function customFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
  return fetch(input, {
    ...init,
    signal: init?.signal || AbortSignal.timeout(300_000),
    // @ts-expect-error dispatcher is a valid option in Node.js undici fetch
    dispatcher: customAgent,
  });
}

export default customFetch;
