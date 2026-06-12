import { tmpdir } from 'os'
import { join } from 'path'
import { mkdirSync, existsSync, readFileSync } from 'fs'
import { NextResponse } from 'next/server'

// ── Shared error response helper ────────────────────────────────────────

/** Return a consistent JSON error response across all API routes */
export function errorJson(message: string, status: number, extra?: Record<string, unknown>) {
  return NextResponse.json({ error: message, ...extra }, { status })
}

// Simple in-memory cache for draw counts (30-second TTL)
const _drawCountCache: Record<string, { count: number; timestamp: number }> = {}
const DRAW_COUNT_TTL = 30 * 1000

// ── Persistent data directory for draw files ──────────────────────────────
const ROOT = process.cwd()
export const DATA_DIR = join(ROOT, 'data', 'draws')

/** Ensure the data directory exists */
export function ensureDataDir(): void {
  if (!existsSync(DATA_DIR)) {
    mkdirSync(DATA_DIR, { recursive: true })
  }
}

/** Get the persistent draw file path for a game */
export function getDrawsFilePath(game: string): string {
  return join(DATA_DIR, `draws_${game}.txt`)
}

/** Count draw lines in a file (lines containing '||') — cached with 5-min TTL */
export function countDrawsInFile(filePath: string): number {
  try {
    if (!existsSync(filePath)) return 0
    const now = Date.now()
    const cached = _drawCountCache[filePath]
    if (cached && (now - cached.timestamp) < DRAW_COUNT_TTL) {
      return cached.count
    }
    const content = readFileSync(filePath, 'utf-8')
    const count = content.split('\n').filter((line: string) => line.trim() && line.includes('||')).length
    _drawCountCache[filePath] = { count, timestamp: now }
    // Evict oldest entries if over limit
    const cacheKeys = Object.keys(_drawCountCache)
    if (cacheKeys.length > 50) {
      const sorted = cacheKeys.sort((a, b) => _drawCountCache[a].timestamp - _drawCountCache[b].timestamp)
      for (let i = 0; i < sorted.length - 50; i++) {
        delete _drawCountCache[sorted[i]]
      }
    }
    return count
  } catch {
    return 0
  }
}

/** Known game identifiers from stoloto.ru */
// Known game identifiers — used only for logging unknown games (not for blocking)
const KNOWN_GAMES = new Set([
  '4x20', '6x45plus', '5x36plus', '5x2', 'keno2',
  '7x49', '5x36', '6x45', '4x20plus', '6x36', '5x50',
  '6x49', 'sportloto4x20', 'gosloto4x20', 'gosloto6x45',
  'gosloto5x36', 'gosloto7x49', 'rapido', 'top3', 'zabegalochka',
  'keno', 'bingo75', 'instant', 'joker', 'gzhl', 'nards-pro',
  'nards-start', 'nards-drive', 'nards-ultra', 'dvazhdydva',
  '5x36lite', '5x36lite2', 'football-gold', 'football-bronze',
  'football-silver', 'football-brilliant', 'oxota', 'oxota-vyzov',
  'spec', 'lovi_moment', 'crazycombo', 'fzp', 'ruslotto',
  '1224', 'ostatki-sladki', 'luckycard', 'zabava',
  'udachanasdachu', 'rapido-drive', 'rapido2', 'rapido-ultra',
  'rocketbingo',
])

// ── Shared Python stdout parser ────────────────────────────────────────────

/** Safely parse Python script stdout — find JSON even if preceded by other text */
export function safeParseStdout(stdout: string): { data?: Record<string, unknown>; error: string } | null {
  if (!stdout || !stdout.trim()) {
    return { error: 'Python script returned empty output' }
  }
  const trimmed = stdout.trim()

  // v39.3.1: Try direct parse first (fast path for clean JSON output)
  if (trimmed[0] === '{' || trimmed[0] === '[') {
    try { return { data: JSON.parse(trimmed) } }
    catch { /* fall through to resilient parsing */ }
  }

  // v39.3.1: Resilient parsing — find the LAST '{' or '[' in the output.
  // This handles cases where libraries or modules print warnings/text before JSON.
  const lastBrace = trimmed.lastIndexOf('{')
  const lastBracket = trimmed.lastIndexOf('[')
  const jsonStart = Math.max(lastBrace, lastBracket)

  if (jsonStart >= 0) {
    // Try to find the matching closing bracket/brace
    const openChar = trimmed[jsonStart]
    const closeChar = openChar === '{' ? '}' : ']'
    // Scan forward for the matching close character (respecting nesting)
    let depth = 0
    for (let i = jsonStart; i < trimmed.length; i++) {
      if (trimmed[i] === openChar) depth++
      else if (trimmed[i] === closeChar) depth--
      if (depth === 0) {
        try {
          const jsonStr = trimmed.substring(jsonStart, i + 1)
          return { data: JSON.parse(jsonStr) }
        } catch { break }
      }
    }
  }

  return { error: `Script returned non-JSON output (starts with "${trimmed.slice(0, 50)}").` }
}

/** Validate a game identifier — only allow alphanumeric + known chars */
export function validateGameId(game: unknown): string | null {
  if (typeof game !== 'string' || game.length === 0 || game.length > 50) {
    return 'Game must be a non-empty string (max 50 chars)'
  }
  // Reject anything that's not alphanumeric, plus, or underscore
  if (!/^[a-z0-9+_]+$/i.test(game)) {
    return 'Game identifier contains invalid characters'
  }
  // Log if unknown game (but allow it — new games may be added)
  if (!KNOWN_GAMES.has(game)) {
    console.warn(`[api] Unknown game identifier: "${game}"`)
  }
  return null
}

/** Validate a file path — must be under DATA_DIR or OS temp directory */
export function validateFilePath(filePath: unknown): string | null {
  if (typeof filePath !== 'string' || filePath.length === 0) {
    return 'File path must be a non-empty string'
  }
  // Reject path traversal
  if (filePath.includes('..')) {
    return 'Path traversal detected'
  }
  // Reject shell metacharacters
  if (!/^[a-zA-Z0-9_\-./\\:]+$/.test(filePath)) {
    return 'File path contains invalid characters'
  }
  // Allow DATA_DIR paths (persistent draw files)
  if (filePath.startsWith(DATA_DIR)) {
    return null
  }
  // Allow OS temp directory paths
  const tmp = tmpdir()
  if (filePath.startsWith(tmp) || filePath.startsWith('/tmp/')) {
    return null
  }
  return 'File path must be under data or temp directory'
}
