import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { safeJsonFetch } from '@/lib/fetch'

const originalFetch = globalThis.fetch

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  globalThis.fetch = originalFetch
})

function mockFetch(response: Partial<Response> & { body?: string; json?: unknown }) {
  const headers = new Headers()
  if (response.headers) {
    const h = response.headers instanceof Headers ? response.headers : new Headers(response.headers as Record<string, string>)
    h.forEach((v, k) => headers.set(k, v))
  }

  return vi.fn().mockResolvedValue({
    ok: response.ok ?? true,
    status: response.status ?? 200,
    headers,
    text: () => Promise.resolve(response.body ?? ''),
    json: () => Promise.resolve(response.json ?? {}),
  } satisfies Response)
}

describe('safeJsonFetch', () => {
  it('returns data and ok:true for successful 200 JSON response', async () => {
    const payload = { status: 'ok', game: '4x20' }
    globalThis.fetch = mockFetch({
      ok: true,
      status: 200,
      headers: { 'content-type': 'application/json' },
      json: payload,
    })

    const result = await safeJsonFetch('/api/test')
    expect(result.ok).toBe(true)
    expect(result.data).toEqual(payload)
  })

  it('returns ok:false for HTTP 500 response', async () => {
    globalThis.fetch = mockFetch({
      ok: false,
      status: 500,
      headers: { 'content-type': 'application/json' },
      json: { error: 'Internal Server Error' },
    })

    const result = await safeJsonFetch('/api/test')
    expect(result.ok).toBe(false)
    expect((result.data as Record<string, unknown>).error).toBeDefined()
  })

  it('returns ok:false on timeout (AbortController)', async () => {
    const abortError = new DOMException('The operation was aborted', 'TimeoutError')
    globalThis.fetch = vi.fn().mockRejectedValue(abortError)

    const result = await safeJsonFetch('/api/test', {}, 100)
    expect(result.ok).toBe(false)
    expect((result.data as Record<string, unknown>).error).toContain('время')
  })

  it('returns ok:false for HTML response (content-type text/html)', async () => {
    globalThis.fetch = mockFetch({
      ok: true,
      status: 200,
      headers: { 'content-type': 'text/html' },
      body: '<html><body>Server Error</body></html>',
      json: undefined,
    })

    const result = await safeJsonFetch('/api/test')
    expect(result.ok).toBe(false)
    expect((result.data as Record<string, unknown>).error).toBeDefined()
  })

  it('returns ok:false on network error (TypeError: Failed to fetch)', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))

    const result = await safeJsonFetch('/api/test')
    expect(result.ok).toBe(false)
    expect((result.data as Record<string, unknown>).error).toBe('Failed to fetch')
  })

  it('returns ok:false when response body is invalid JSON', async () => {
    // Return a Response-like where .json() throws
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: () => Promise.resolve('{broken json'),
      json: () => Promise.reject(new SyntaxError('Unexpected token')),
    } satisfies Response)

    const result = await safeJsonFetch('/api/test')
    expect(result.ok).toBe(false)
    expect((result.data as Record<string, unknown>).error).toBeDefined()
  })
})
