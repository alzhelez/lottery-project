/**
 * Smoke test: safeParseStdout robustness from @/lib/api-utils
 *
 * Verifies the JSON parser handles all edge cases without crashing:
 * binary-like strings, very long strings, unicode, deeply nested objects,
 * primitive types, and malformed JSON-like strings.
 */
import { describe, it, expect } from 'vitest'
import { safeParseStdout } from '@/lib/api-utils'

describe('safeParseStdout robustness', () => {
  it('returns error for empty string', () => {
    const result = safeParseStdout('')
    expect(result).not.toBeNull()
    expect(result).toHaveProperty('error')
  })

  it('returns error for whitespace-only string', () => {
    const result = safeParseStdout('   \n\t  ')
    expect(result).not.toBeNull()
    expect(result).toHaveProperty('error')
  })

  it('returns null/error for null input', () => {
    // @ts-expect-error — intentionally passing invalid type
    const result = safeParseStdout(null)
    expect(result).toHaveProperty('error')
  })

  it('handles binary-like strings with null bytes', () => {
    const binaryInput = '\x00\x01\x02hello'
    const result = safeParseStdout(binaryInput)
    expect(result).not.toBeNull()
    // Should not crash — either returns error or data
    expect(result).toHaveProperty('error')
  })

  it('handles very long strings (100KB)', () => {
    // Create a very long string that is NOT valid JSON
    const longString = 'x'.repeat(100_000)
    const result = safeParseStdout(longString)
    expect(result).not.toBeNull()
    expect(result).toHaveProperty('error')
  })

  it('handles very long valid JSON', () => {
    const bigArray = JSON.stringify({ items: Array.from({ length: 5000 }, (_, i) => i) })
    const result = safeParseStdout(bigArray)
    expect(result).not.toBeNull()
    expect(result).toHaveProperty('data')
  })

  it('parses valid JSON with unicode/emoji', () => {
    const input = JSON.stringify({ message: 'Привет мир 🌍🎮', status: 'ok', items: ['测试', '🎉'] })
    const result = safeParseStdout(input)
    expect(result).toHaveProperty('data')
    expect((result!.data as Record<string, unknown>).message).toBe('Привет мир 🌍🎮')
  })

  it('parses valid JSON with deeply nested objects', () => {
    let deep: Record<string, unknown> = { level: 'bottom' }
    for (let i = 0; i < 100; i++) {
      deep = { child: deep }
    }
    const input = JSON.stringify(deep)
    const result = safeParseStdout(input)
    expect(result).toHaveProperty('data')
    expect(result!.data).toBeDefined()
  })

  it('handles number string "123" gracefully', () => {
    const result = safeParseStdout('123')
    expect(result).toHaveProperty('error')
  })

  it('handles boolean string "true" gracefully', () => {
    const result = safeParseStdout('true')
    expect(result).toHaveProperty('error')
  })

  it('handles strings that look like JSON but are not', () => {
    const malformed = '{this is not valid json}'
    const result = safeParseStdout(malformed)
    expect(result).toHaveProperty('error')
  })

  it('handles truncated JSON', () => {
    const truncated = '{"key": "value", "incomplete":'
    const result = safeParseStdout(truncated)
    expect(result).toHaveProperty('error')
  })

  it('handles plain text output', () => {
    const result = safeParseStdout('Some Python error traceback here')
    expect(result).toHaveProperty('error')
  })

  it('never throws on any input', () => {
    const inputs = [
      '', '   ', null, undefined, '\x00',
      'x'.repeat(200_000),
      JSON.stringify({ a: '\u0000' }),
      '[',
      '{bad json',
    ]
    for (const input of inputs) {
      expect(() => safeParseStdout(input as string)).not.toThrow()
    }
  })

  it('parses valid JSON array', () => {
    const input = JSON.stringify([1, 2, 3, 'four', { five: 5 }])
    const result = safeParseStdout(input)
    expect(result).toHaveProperty('data')
  })
})
