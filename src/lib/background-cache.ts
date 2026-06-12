/**
 * Shared background-cache utility for predict and pipeline API routes.
 * Eliminates ~100 lines of duplicated cache + polling logic.
 */

import { NextResponse } from 'next/server'
import { existsSync, statSync } from 'fs'
import { validateGameId, validateFilePath, safeParseStdout, getDrawsFilePath, errorJson } from '@/lib/api-utils'
import { runPythonScript } from '@/lib/python-runner'
import { rateLimit } from '@/lib/rate-limit'

// ── Types ────────────────────────────────────────────────────────────────

interface CacheEntry {
  result: Record<string, unknown>
  timestamp: number
  game: string
  fileModTime: number
  ttl?: number
}

interface CacheConfig {
  cacheTtl?: number
  maxCacheEntries?: number
  rateLimitMax?: number
  rateLimitWindowMs?: number
  scriptName: string
  scriptArgs?: (game: string, file: string, extra?: Record<string, unknown>) => string[]
  timeoutMs?: number
  operationLabel: string
}

// ── In-memory stores (per-operation) ────────────────────────────────────

const caches = new Map<string, Record<string, CacheEntry>>()
const refreshing = new Map<string, Record<string, boolean>>()

// ── Cache helpers ────────────────────────────────────────────────────────

function getCache(operation: string): Record<string, CacheEntry> {
  if (!caches.has(operation)) caches.set(operation, {})
  return caches.get(operation)!
}

function getRefreshing(operation: string): Record<string, boolean> {
  if (!refreshing.has(operation)) refreshing.set(operation, {})
  return refreshing.get(operation)!
}

function evictOldCacheEntries(cache: Record<string, CacheEntry>, max: number) {
  const keys = Object.keys(cache)
  if (keys.length > max) {
    const sorted = keys.sort((a, b) => cache[a].timestamp - cache[b].timestamp)
    for (let i = 0; i < sorted.length - max; i++) {
      delete cache[sorted[i]]
    }
  }
}

// ── Main handler ─────────────────────────────────────────────────────────

/**
 * Create a POST handler for a background-cached Python operation.
 * Handles: validation, rate limiting, cache check, background execution, polling.
 */
export function createCachedOperationHandler(config: CacheConfig) {
  const {
    cacheTtl = 30 * 60 * 1000,
    maxCacheEntries = 20,
    rateLimitMax = 3,
    rateLimitWindowMs = 60_000,
    scriptName,
    scriptArgs = (_game, _file) => [],
    timeoutMs = 600_000,
    operationLabel,
  } = config

  return async function handler(request: Request, extraBody?: Record<string, unknown>) {
    try {
      const body = await request.json()
      const { game, data_file } = body
      const extra = extraBody || body

      // Rate limit
      const rl = rateLimit(`${operationLabel}-${game || 'unknown'}`, rateLimitMax, rateLimitWindowMs)
      if (!rl.allowed) {
        return errorJson(
          `Слишком много запросов. Подождите ${Math.ceil(rl.resetIn / 1000)}с и попробуйте снова.`,
          429,
          { retry_after: Math.ceil(rl.resetIn / 1000) },
        )
      }

      // Validate game
      const gameErr = validateGameId(game)
      if (gameErr) return errorJson(gameErr, 400)

      // Resolve file path
      const file = data_file || (game ? getDrawsFilePath(game) : null)
      if (file) {
        const fileErr = validateFilePath(file)
        if (fileErr) return errorJson(fileErr, 400)
      }
      if (!file) {
        return errorJson('Missing "data_file" or "game" parameter in request body', 400)
      }
      if (!existsSync(file)) {
        return errorJson(
          'Файл данных не найден. Сначала загрузите тиражи.',
          400,
          { hint: 'Перейдите к шагу 2 и нажмите "Загрузить все тиражи".' },
        )
      }

      const fileStat = statSync(file)
      const cacheKey = game || 'unknown'
      const now = Date.now()
      const cache = getCache(operationLabel)
      const refreshingMap = getRefreshing(operationLabel)

      // ── Cache hit: return immediately ──────────────────────────────────
      const cached = cache[cacheKey]
      if (cached && (now - cached.timestamp) < (cached.ttl || cacheTtl) && cached.fileModTime >= fileStat.mtimeMs) {
        console.log(`[api/${operationLabel}] Cache hit: ${game} (${Math.round((now - cached.timestamp) / 1000)}s ago)`)
        return NextResponse.json({
          ...cached.result,
          _cached: true,
          _cache_age_seconds: Math.round((now - cached.timestamp) / 1000),
        })
      }

      // ── Start background operation if not already running ──────────────
      if (!refreshingMap[cacheKey]) {
        refreshingMap[cacheKey] = true
        const args = scriptArgs(game || 'unknown', file, extra)
        _backgroundRun(operationLabel, cacheKey, game, file, scriptName, args, timeoutMs, cache, refreshingMap, maxCacheEntries)
          .finally(() => { refreshingMap[cacheKey] = false })
      }

      // Return stale cache if available
      if (cached) {
        console.log(`[api/${operationLabel}] Stale cache returned for ${game}, refreshing in background`)
        return NextResponse.json({
          ...cached.result,
          _cached: true,
          _refreshing: true,
          _message: `Обновление ${operationLabel} в фоновом режиме...`,
        })
      }

      // No cache — return pending
      console.log(`[api/${operationLabel}] No cache for ${game}, started background operation`)
      return NextResponse.json({
        status: 'pending',
        _refreshing: true,
        _message: `${operationLabel} формируется в фоновом режиме. Данные появятся автоматически.`,
      })
    } catch (error) {
      return errorJson(error instanceof Error ? error.message : 'Unknown error', 500)
    }
  }
}

// ── Background execution ─────────────────────────────────────────────────

async function _backgroundRun(
  operationLabel: string,
  cacheKey: string,
  game: string,
  file: string,
  scriptName: string,
  args: string[],
  timeoutMs: number,
  cache: Record<string, CacheEntry>,
  refreshingMap: Record<string, boolean>,
  maxCacheEntries: number,
) {
  const errorTtl = 30_000 // 30 seconds for error results

  const storeError = (error: string, hint?: string) => {
    cache[cacheKey] = {
      result: { status: 'error', error, hint: hint || 'Попробуйте снова.' },
      timestamp: Date.now(),
      game,
      fileModTime: existsSync(file) ? statSync(file).mtimeMs : 0,
      ttl: errorTtl,
    }
    evictOldCacheEntries(cache, maxCacheEntries)
  }

  try {
    console.log(`[api/${operationLabel}] Background operation started for ${game}...`)

    const { stdout, stderr, code } = await runPythonScript(scriptName, args, { timeout: timeoutMs })

    console.log(`[api/${operationLabel}] Background operation finished: code=${code}, stdout_len=${stdout?.length || 0}`)

    if (code !== 0) {
      console.error(`[api/${operationLabel}] Failed for ${game}: code=${code}, stderr=${stderr?.slice(-200)}`)
      storeError(`Ошибка анализа: код ${code}`, stderr?.slice(-300))
      return
    }

    const parsed = safeParseStdout(stdout || '')
    if (!parsed || !parsed.data) {
      console.error(`[api/${operationLabel}] Failed to parse output for ${game}`)
      storeError('Не удалось обработать результат.', parsed?.error)
      return
    }

    const fileModTime = existsSync(file) ? statSync(file).mtimeMs : 0
    cache[cacheKey] = {
      result: parsed.data as Record<string, unknown>,
      timestamp: Date.now(),
      game,
      fileModTime,
    }
    evictOldCacheEntries(cache, maxCacheEntries)
    console.log(`[api/${operationLabel}] Cached result for ${game}`)
  } catch (err) {
    console.error(`[api/${operationLabel}] Background exception for ${game}:`, err)
    storeError('Внутренняя ошибка.', err instanceof Error ? err.message : undefined)
  }
}
