import { describe, it, expect, vi } from 'vitest'
import { validateGameId, validateFilePath, DATA_DIR } from '@/lib/api-utils'

describe('validateGameId', () => {
  it('returns null for a valid known game', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(validateGameId('4x20')).toBeNull()
    expect(warnSpy).not.toHaveBeenCalled()
    warnSpy.mockRestore()
  })

  it('returns error for empty string', () => {
    expect(validateGameId('')).toBe('Game must be a non-empty string (max 50 chars)')
  })

  it('returns error for string longer than 50 chars', () => {
    const longName = 'a'.repeat(51)
    expect(validateGameId(longName)).toBe('Game must be a non-empty string (max 50 chars)')
  })

  it('returns error for string with spaces', () => {
    expect(validateGameId('4x 20')).toBe('Game identifier contains invalid characters')
  })

  it('returns error for path traversal attempt', () => {
    expect(validateGameId('../etc/passwd')).toBe('Game identifier contains invalid characters')
  })

  it('allows unknown game names (warns but returns null)', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(validateGameId('newgame123')).toBeNull()
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('Unknown game'))
    warnSpy.mockRestore()
  })

  it('returns error for non-string input (number)', () => {
    expect(validateGameId(42)).toBe('Game must be a non-empty string (max 50 chars)')
  })

  it('returns error for null input', () => {
    expect(validateGameId(null)).toBe('Game must be a non-empty string (max 50 chars)')
  })
})

describe('validateFilePath', () => {
  it('allows path under /tmp/', () => {
    expect(validateFilePath('/tmp/draws_4x20.txt')).toBeNull()
  })

  it('rejects path with ".." (path traversal)', () => {
    expect(validateFilePath('/tmp/../etc/passwd')).toBe('Path traversal detected')
  })

  it('rejects shell metacharacter "|"', () => {
    expect(validateFilePath('/tmp/file|cat')).toBe('File path contains invalid characters')
  })

  it('rejects shell metacharacter "&"', () => {
    expect(validateFilePath('/tmp/file&bg')).toBe('File path contains invalid characters')
  })

  it('rejects shell metacharacter ";"', () => {
    expect(validateFilePath('/tmp/file;rm')).toBe('File path contains invalid characters')
  })

  it('returns error for empty string', () => {
    expect(validateFilePath('')).toBe('File path must be a non-empty string')
  })

  it('returns error for non-string input', () => {
    expect(validateFilePath(123)).toBe('File path must be a non-empty string')
  })

  it('returns error for null input', () => {
    expect(validateFilePath(null)).toBe('File path must be a non-empty string')
  })

  it('allows paths under DATA_DIR', () => {
    expect(validateFilePath(`${DATA_DIR}/draws_4x20.txt`)).toBeNull()
  })

  it('rejects arbitrary paths not under data or temp', () => {
    expect(validateFilePath('/home/user/file.txt')).toBe('File path must be under data or temp directory')
  })
})
