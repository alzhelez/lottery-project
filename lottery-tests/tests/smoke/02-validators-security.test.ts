/**
 * Smoke test: security validators from @/lib/api-utils
 *
 * Verifies validateGameId and validateFilePath reject ALL attack vectors,
 * never throw, and accept valid inputs.
 */
import { describe, it, expect } from 'vitest'
import { validateGameId, validateFilePath } from '@/lib/api-utils'

describe('validateGameId', () => {
  it('rejects empty string', () => {
    const result = validateGameId('')
    expect(result).toBeTypeOf('string')
    expect(result).not.toBeNull()
  })

  it('rejects non-string input', () => {
    expect(validateGameId(undefined)).toBeTypeOf('string')
    expect(validateGameId(null)).toBeTypeOf('string')
    expect(validateGameId(123)).toBeTypeOf('string')
    expect(validateGameId({})).toBeTypeOf('string')
    expect(validateGameId([])).toBeTypeOf('string')
    expect(validateGameId(true)).toBeTypeOf('string')
  })

  it('rejects path traversal', () => {
    expect(validateGameId('../etc/passwd')).toBeTypeOf('string')
    expect(validateGameId('..')).toBeTypeOf('string')
    expect(validateGameId('foo/../bar')).toBeTypeOf('string')
  })

  it('rejects shell injection attempts', () => {
    expect(validateGameId(';rm -rf /')).toBeTypeOf('string')
    expect(validateGameId('$(whoami)')).toBeTypeOf('string')
    expect(validateGameId('`id`')).toBeTypeOf('string')
    expect(validateGameId('| cat /etc/shadow')).toBeTypeOf('string')
    expect(validateGameId('&& echo pwned')).toBeTypeOf('string')
  })

  it('rejects unicode tricks', () => {
    expect(validateGameId('\u00004x20')).toBeTypeOf('string')  // null byte prefix
    expect(validateGameId('4x20<script>')).toBeTypeOf('string') // HTML injection
    expect(validateGameId('4x20\n5x36')).toBeTypeOf('string')  // newline
    expect(validateGameId('4x20\ttab')).toBeTypeOf('string')    // tab
    expect(validateGameId('4x20<script>alert(1)</script>')).toBeTypeOf('string')
  })

  it('accepts valid known game IDs', () => {
    expect(validateGameId('4x20')).toBeNull()
    expect(validateGameId('5x36')).toBeNull()
    expect(validateGameId('7x49')).toBeNull()
    expect(validateGameId('6x45plus')).toBeNull()
    expect(validateGameId('5x36plus')).toBeNull()
    expect(validateGameId('keno2')).toBeNull()
    expect(validateGameId('rapido')).toBeNull()
  })

  it('never throws even on extreme inputs', () => {
    const dangerousInputs = [
      '', null, undefined, 42, true, false,
      '../' + '../'.repeat(100),
      'A'.repeat(10000),
      '\x00',
      { toString: () => { throw new Error('boom') } },
    ]
    for (const input of dangerousInputs) {
      expect(() => validateGameId(input)).not.toThrow()
    }
  })
})

describe('validateFilePath', () => {
  it('rejects path traversal attempts', () => {
    expect(validateFilePath('../etc/passwd')).toBeTypeOf('string')
    expect(validateFilePath('..')).toBeTypeOf('string')
    expect(validateFilePath('foo/../../etc/shadow')).toBeTypeOf('string')
    expect(validateFilePath('/etc/shadow')).toBeTypeOf('string')
  })

  it('rejects shell metacharacters', () => {
    expect(validateFilePath('| cat /etc/passwd')).toBeTypeOf('string')
    expect(validateFilePath('; rm -rf /')).toBeTypeOf('string')
    expect(validateFilePath('& whoami')).toBeTypeOf('string')
    expect(validateFilePath('$(whoami)')).toBeTypeOf('string')
    expect(validateFilePath('`id`')).toBeTypeOf('string')
  })

  it('rejects non-string and empty input', () => {
    expect(validateFilePath('')).toBeTypeOf('string')
    expect(validateFilePath(null)).toBeTypeOf('string')
    expect(validateFilePath(undefined)).toBeTypeOf('string')
    expect(validateFilePath(123)).toBeTypeOf('string')
  })

  it('accepts /tmp/ paths', () => {
    expect(validateFilePath('/tmp/somefile.txt')).toBeNull()
    expect(validateFilePath('/tmp/nested/dir/file.json')).toBeNull()
  })

  it('never throws even on extreme inputs', () => {
    const dangerousInputs = [
      '', null, undefined, 42, true,
      '../../../' + '../'.repeat(100),
      '; rm -rf /',
      '$(rm -rf /)',
      '`cat /etc/shadow`',
      '/etc/passwd\x00',
      { toString: () => { throw new Error('boom') } },
    ]
    for (const input of dangerousInputs) {
      expect(() => validateFilePath(input)).not.toThrow()
    }
  })
})
