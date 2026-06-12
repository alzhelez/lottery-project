import { describe, it, expect, vi } from 'vitest'
import { safeParseStdout } from '@/lib/api-utils'

describe('safeParseStdout', () => {
  it('parses a valid JSON object', () => {
    const result = safeParseStdout('{"status":"ok","game":"4x20"}')
    expect(result).toEqual({ data: { status: 'ok', game: '4x20' } })
  })

  it('parses a valid JSON array', () => {
    const result = safeParseStdout('[1, 2, 3]')
    expect(result).toEqual({ data: [1, 2, 3] })
  })

  it('returns error for invalid JSON', () => {
    const result = safeParseStdout('{"broken json"')
    expect(result).not.toBeNull()
    expect(result!.error).toContain('Failed to parse')
  })

  it('returns error for empty string', () => {
    const result = safeParseStdout('')
    expect(result).toEqual({ error: 'Python script returned empty output' })
  })

  it('returns error for whitespace-only string', () => {
    const result = safeParseStdout('   \n\t  ')
    expect(result).toEqual({ error: 'Python script returned empty output' })
  })

  it('returns error for non-JSON text like Traceback', () => {
    const result = safeParseStdout('Traceback (most recent call last):\n  File "predict.py", line 42')
    expect(result).not.toBeNull()
    expect(result!.error).toContain('non-JSON')
  })

  it('returns error for null input (treated as empty)', () => {
    const result = safeParseStdout(null as unknown as string)
    expect(result).toEqual({ error: 'Python script returned empty output' })
  })

  it('returns error for undefined input (treated as empty)', () => {
    const result = safeParseStdout(undefined as unknown as string)
    expect(result).toEqual({ error: 'Python script returned empty output' })
  })

  it('returns non-JSON error for the string "null" (does not start with { or [)', () => {
    const result = safeParseStdout('null')
    expect(result!.error).toContain('non-JSON')
  })

  it('trims whitespace around valid JSON and parses correctly', () => {
    const result = safeParseStdout('  \n  {"key": "value"}  \n  ')
    expect(result).toEqual({ data: { key: 'value' } })
  })

  it('trims whitespace around valid JSON array and parses correctly', () => {
    const result = safeParseStdout('  [1,2,3]  ')
    expect(result).toEqual({ data: [1, 2, 3] })
  })
})
