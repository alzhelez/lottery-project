import { NextResponse } from 'next/server'
import { validateGameId, safeParseStdout, ensureDataDir, getDrawsFilePath, countDrawsInFile, errorJson } from '@/lib/api-utils'
import { runPythonScript } from '@/lib/python-runner'
import { rateLimit } from '@/lib/rate-limit'

// Track which games are currently being refreshed in the background
const _refreshing: Record<string, boolean> = {}
const _refreshStart: Record<string, number> = {}
const REFRESH_MAX_DURATION = 15 * 60 * 1000 // 15 minutes (games with 10k+ draws need more time)
const _lastRefreshDone: Record<string, number> = {}
const REFRESH_COOLDOWN = 60_000 // 1 minute cooldown between background refreshes

/** Remove stale entries from tracking maps to prevent unbounded growth */
function _cleanupStaleEntries() {
  const cutoff = Date.now() - REFRESH_COOLDOWN
  for (const key of Object.keys(_lastRefreshDone)) {
    if (_lastRefreshDone[key] < cutoff) {
      delete _lastRefreshDone[key]
      delete _refreshing[key]
      delete _refreshStart[key]
    }
  }
}

export async function POST(request: Request) {
  try {
    // Safely parse body — handle empty/malformed requests gracefully
    let body: Record<string, unknown> = {}
    try {
      const rawBody = await request.text()
      if (rawBody.trim()) {
        body = JSON.parse(rawBody)
      }
    } catch {
      return errorJson('Неверный формат запроса. Ожидается JSON с полем "game".', 400)
    }
    const { game } = body

    if (!game || typeof game !== 'string') {
      return errorJson('Missing "game" parameter in request body', 400)
    }

    const gameErr = validateGameId(game)
    if (gameErr) {
      return errorJson(gameErr, 400)
    }

    // Clean up stale tracking entries
    _cleanupStaleEntries()

    // Check if refresh has been running too long — auto-stop
    if (_refreshStart[game] && (Date.now() - _refreshStart[game]) > REFRESH_MAX_DURATION) {
      _refreshing[game] = false
      delete _refreshStart[game]
    }

    // Ensure data directory exists
    ensureDataDir()

    const outputFile = getDrawsFilePath(game)
    const totalDraws = countDrawsInFile(outputFile)

    // ── Cache-first: return immediately if file exists ──────────────────────
    if (totalDraws > 0) {
      console.log(`[api/fetch-draws] Cache hit: ${game} has ${totalDraws} draws at ${outputFile}`)

      // If not already refreshing in background, start a background update
      // Check cooldown before starting background refresh
      const lastDone = _lastRefreshDone[game] || 0
      const cooldownLeft = REFRESH_COOLDOWN - (Date.now() - lastDone)
      if (cooldownLeft > 0) {
        // Recently refreshed — return cache without starting new refresh
        return NextResponse.json({
          game,
          total_draws: totalDraws,
          data_file: outputFile,
          _refreshing: false,
          _cooldown_seconds: Math.ceil(cooldownLeft / 1000),
        })
      }

      if (!_refreshing[game]) {
        _refreshing[game] = true
        _refreshStart[game] = Date.now()
        // Fire-and-forget background refresh
        _backgroundRefresh(game, outputFile).finally(() => {
          _refreshing[game] = false
          delete _refreshStart[game]
        })
      }

      return NextResponse.json({
        game,
        total_draws: totalDraws,
        data_file: outputFile,
        _refreshing: _refreshing[game],
        _refresh_elapsed: _refreshStart[game] ? Date.now() - _refreshStart[game] : 0,
        _refresh_max: REFRESH_MAX_DURATION,
        _message: 'Загружено из кэша. Обновление в фоновом режиме...',
      })
    }

    // ── No cache: start background fetch, return immediately ────────────────
    // Rate-limit only the expensive operation (starting a new background fetch)
    const noCacheRl = rateLimit(`fetch-nocache-${game}`, 2, 60_000)
    if (!noCacheRl.allowed) {
      return errorJson(
          `Слишком много запросов на загрузку. Подождите ${Math.ceil(noCacheRl.resetIn / 1000)}с.`,
          429,
          { retry_after: Math.ceil(noCacheRl.resetIn / 1000) },
      )
    }

    console.log(`[api/fetch-draws] No cache for ${game}, starting background fetch...`)

    if (!_refreshing[game]) {
      _refreshing[game] = true
      _refreshStart[game] = Date.now()
      // Fire-and-forget background fetch
      _backgroundRefresh(game, outputFile).finally(() => {
        _refreshing[game] = false
        delete _refreshStart[game]
      })
    }

    return NextResponse.json({
      game,
      total_draws: 0,
      data_file: outputFile,
      _refreshing: true,
      _refresh_elapsed: _refreshStart[game] ? Date.now() - _refreshStart[game] : 0,
      _refresh_max: REFRESH_MAX_DURATION,
      _message: 'Загрузка тиражей начата. Подождите и нажмите "Загрузить" снова.',
    })
  } catch (error) {
    console.error(`[api/fetch-draws] Exception:`, error)
    return errorJson(error instanceof Error ? error.message : 'Unknown error', 500)
  }
}

/**
 * Background refresh: runs Python fetch script without blocking the HTTP response.
 * Uses shorter timeout (15s quick attempt) for the first try, then 10 min for full.
 */
async function _backgroundRefresh(game: string, outputFile: string): Promise<void> {
  try {
    console.log(`[api/fetch-draws] Background refresh started for ${game}...`)

    // v26.0: runPythonScript has its own timeout, no AbortController needed
    const { stdout, stderr, code } = await runPythonScript('fetch.py', [
      '--game', game, '--output', outputFile,
    ], {
      timeout: REFRESH_MAX_DURATION,
    })

    console.log(`[api/fetch-draws] Background refresh finished: code=${code}, stdout_len=${stdout?.length || 0}`)

    if (code === 0) {
      const finalCount = countDrawsInFile(outputFile)
      console.log(`[api/fetch-draws] Background refresh: ${game} now has ${finalCount} draws`)
    } else if (code === null) {
      console.warn(`[api/fetch-draws] Background refresh timed out (killed) for ${game}`)
    } else {
      console.warn(`[api/fetch-draws] Background refresh failed for ${game}: code=${code}`)
      if (stderr) {
        console.warn(`[api/fetch-draws] stderr: ${stderr.slice(-300)}`)
      }
    }
  } catch (err) {
    console.error(`[api/fetch-draws] Background refresh exception for ${game}:`, err)
  } finally {
    _lastRefreshDone[game] = Date.now()
  }
}
