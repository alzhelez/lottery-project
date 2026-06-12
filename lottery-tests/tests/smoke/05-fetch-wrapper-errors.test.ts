/**
 * Smoke test: safeJsonFetch error handling from @/lib/fetch
 *
 * Verifies the fetch wrapper handles every error category:
 * success, HTTP errors, network failures, aborts, wrong content-type, empty body.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { safeJsonFetch } from '@/lib/fetch'

// Store original fetch
const originalFetch = globalThis.fetch

describe('safeJsonFetch error handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('successful request with complex nested JSON', async () => {
    const complexData = {
      status: 'ok',
      nested: {
        level1: { level2: { level3: [1, 2, { deep: true }] } },
      },
      items: Array.from({ length: 10 }, (_, i) => ({ id: i, name: `item-${i}` })),
    }

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve(complexData),
    })

    const result = await safeJsonFetch('/api/test')
    expect(result.ok).toBe(true)
    expect(result.data.status).toBe('ok')
    expect(result.data.nested.level1.level2.level3).toHaveLength(3)
    expect(result.data.items).toHaveLength(10)
  })

  it('HTTP 404 with JSON error body', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ error: 'Not found' }),
    })

    const result = await safeJsonFetch('/api/missing')
    expect(result.ok).toBe(false)
    expect(result.data.error).toBe('Not found')
  })

  it('HTTP 403 Forbidden', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: () => Promise.resolve('Forbidden'),
    })

    const result = await safeJsonFetch('/api/forbidden')
    expect(result.ok).toBe(false)
    expect(result.data.error).toBeDefined()
  })

  it('HTTP 502 Bad Gateway', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      headers: new Headers({ 'content-type': 'text/html' }),
      text: () => Promise.resolve('<html><body><h1>502 Bad Gateway</h1></body></html>'),
    })

    const result = await safeJsonFetch('/api/bad')
    expect(result.ok).toBe(false)
    expect(result.data.error).toBeDefined()
  })

  it('network failure (TypeError)', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))

    const result = await safeJsonFetch('/api/network-error')
    expect(result.ok).toBe(false)
    expect(result.data.error).toBeDefined()
  })

  it('AbortError handling', async () => {
    const abortError = new DOMException('The operation was aborted', 'AbortError')
    globalThis.fetch = vi.fn().mockRejectedValue(abortError)

    const result = await safeJsonFetch('/api/abort')
    expect(result.ok).toBe(false)
    expect(result.data.error).toBeDefined()
  })

  it('response with content-type text/plain but parseable JSON', async () => {
    const jsonData = '{"result":"parsed from text"}'
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: () => Promise.resolve(jsonData),
    })

    const result = await safeJsonFetch('/api/text-json')
    expect(result.ok).toBe(true)
    expect(result.data.result).toBe('parsed from text')
  })

  it('response with content-type text/plain with non-JSON body', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: () => Promise.resolve('This is just plain text'),
    })

    const result = await safeJsonFetch('/api/text-plain')
    expect(result.ok).toBe(false)
    expect(result.data.error).toBeDefined()
  })

  it('empty response body (200 but no content)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve(null),
    })

    const result = await safeJsonFetch('/api/empty')
    expect(result.ok).toBe(true)
    expect(result.data).toBeDefined()
  })

  it('HTTP error with HTML response body', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: new Headers({ 'content-type': 'text/html' }),
      text: () => Promise.resolve('<html><body>Internal Server Error</body></html>'),
    })

    const result = await safeJsonFetch('/api/server-error')
    expect(result.ok).toBe(false)
    expect(result.data.error).toBeDefined()
  })
})
