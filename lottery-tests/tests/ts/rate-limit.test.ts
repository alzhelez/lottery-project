import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

describe('rateLimit', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('first request is allowed with remaining = maxRequests - 1', async () => {
    vi.setSystemTime(Date.now())
    const { rateLimit } = await import('@/lib/rate-limit')
    const result = rateLimit('test-key', 5, 60_000)

    expect(result.allowed).toBe(true)
    expect(result.remaining).toBe(4)
    expect(result.resetIn).toBe(60_000)
  })

  it('returns allowed=false and remaining=0 when limit is exceeded', async () => {
    vi.setSystemTime(Date.now())
    const { rateLimit } = await import('@/lib/rate-limit')

    // Use up all 3 allowed requests
    rateLimit('key', 3, 60_000)
    rateLimit('key', 3, 60_000)
    rateLimit('key', 3, 60_000)

    // 4th request should be rejected
    const result = rateLimit('key', 3, 60_000)
    expect(result.allowed).toBe(false)
    expect(result.remaining).toBe(0)
    expect(result.resetIn).toBeGreaterThan(0)
  })

  it('different keys are independent', async () => {
    vi.setSystemTime(Date.now())
    const { rateLimit } = await import('@/lib/rate-limit')

    // Exhaust key-a
    rateLimit('key-a', 2, 60_000)
    rateLimit('key-a', 2, 60_000)
    const rejected = rateLimit('key-a', 2, 60_000)
    expect(rejected.allowed).toBe(false)

    // key-b should still be allowed
    const allowed = rateLimit('key-b', 2, 60_000)
    expect(allowed.allowed).toBe(true)
    expect(allowed.remaining).toBe(1)
  })

  it('evicts oldest entries when more than 500 unique keys are created', async () => {
    vi.setSystemTime(Date.now())
    const { rateLimit } = await import('@/lib/rate-limit')

    // Create 501 unique keys — the eviction threshold is MAX_ENTRIES=500
    // The _evict() function runs on each new key creation (first request for that key)
    const keys = Array.from({ length: 501 }, (_, i) => `key-${i}`)
    for (const key of keys) {
      rateLimit(key, 5, 60_000)
    }

    // The oldest key (key-0) should have been evicted because we exceeded 500
    // Since all were created at the same time and no entries are expired,
    // the eviction removes oldest (earliest resetTime). All resetTimes are the same,
    // so entries are sorted by resetTime and the first ones removed.
    // After creating 501 entries, eviction keeps only 500.
    // Request key-0 again — it should be treated as a new entry (allowed)
    const result = rateLimit('key-0', 5, 60_000)
    expect(result.allowed).toBe(true)
    expect(result.remaining).toBe(4) // Fresh entry, not the old one
  })

  it('resets the window after time expires', async () => {
    const now = Date.now()
    vi.setSystemTime(now)
    const { rateLimit } = await import('@/lib/rate-limit')

    // Use up the limit
    rateLimit('key', 2, 10_000)
    rateLimit('key', 2, 10_000)
    const rejected = rateLimit('key', 2, 10_000)
    expect(rejected.allowed).toBe(false)

    // Advance past the window
    vi.setSystemTime(now + 10_001)
    const allowed = rateLimit('key', 2, 10_000)
    expect(allowed.allowed).toBe(true)
    expect(allowed.remaining).toBe(1)
  })
})
