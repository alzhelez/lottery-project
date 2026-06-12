/**
 * Smoke test: rate limiter resilience from @/lib/rate-limit
 *
 * Verifies rateLimit doesn't crash under unusual inputs: extreme values,
 * empty/long keys, and rapid burst of requests.
 */
import { describe, it, expect, beforeEach } from 'vitest'

// rate-limit uses module-level state, so we import it fresh each test
// by re-importing. But since vitest caches modules, we use unique keys.
import { rateLimit } from '@/lib/rate-limit'

describe('rateLimit resilience', () => {
  it('handles very high maxRequests without crashing', () => {
    const result = rateLimit('smoke-high-max', 999999, 60_000)
    expect(result).toHaveProperty('allowed')
    expect(result).toHaveProperty('remaining')
    expect(result).toHaveProperty('resetIn')
    expect(result.allowed).toBe(true)
  })

  it('handles zero maxRequests (immediate block on second call)', () => {
    // First call creates entry
    const first = rateLimit('smoke-zero-max', 0, 60_000)
    expect(first.allowed).toBe(true)
    // Second call should be blocked since count >= 0
    const second = rateLimit('smoke-zero-max', 0, 60_000)
    expect(second.allowed).toBe(false)
  })

  it('handles very short windowMs (1ms)', () => {
    const result = rateLimit('smoke-short-window', 5, 1)
    expect(result).toHaveProperty('allowed')
    expect(result.allowed).toBe(true)
    expect(result.resetIn).toBeLessThanOrEqual(1)
  })

  it('handles very long windowMs (24 hours)', () => {
    const result = rateLimit('smoke-long-window', 5, 24 * 60 * 60 * 1000)
    expect(result).toHaveProperty('allowed')
    expect(result.allowed).toBe(true)
    expect(result.resetIn).toBeGreaterThan(0)
  })

  it('handles empty string key without crashing', () => {
    const result = rateLimit('', 5, 60_000)
    expect(result).toHaveProperty('allowed')
  })

  it('handles very long key (1000 chars) without crashing', () => {
    const longKey = 'k'.repeat(1000)
    const result = rateLimit(longKey, 5, 60_000)
    expect(result).toHaveProperty('allowed')
    expect(result.allowed).toBe(true)
  })

  it('handles rapid burst of 1000 requests', () => {
    // Use a unique key with very high limit to avoid blocking
    const key = 'smoke-burst-1000'
    let allPassed = true
    for (let i = 0; i < 1000; i++) {
      const result = rateLimit(key, 10000, 60_000)
      if (!result.allowed) {
        allPassed = false
        break
      }
    }
    expect(allPassed).toBe(true)
  })

  it('correctly blocks after exceeding limit', () => {
    const key = 'smoke-block-after-limit'
    // Burn through 5 requests
    for (let i = 0; i < 5; i++) {
      rateLimit(key, 5, 60_000)
    }
    // 6th should be blocked
    const blocked = rateLimit(key, 5, 60_000)
    expect(blocked.allowed).toBe(false)
    expect(blocked.remaining).toBe(0)
  })

  it('result always has correct shape', () => {
    const result = rateLimit('smoke-shape-check', 3, 5000)
    expect(typeof result.allowed).toBe('boolean')
    expect(typeof result.remaining).toBe('number')
    expect(typeof result.resetIn).toBe('number')
  })
})
