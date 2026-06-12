import { NextResponse } from 'next/server'
import { runPythonScript } from '@/lib/python-runner'
import { existsSync, readFileSync, statSync } from 'fs'
import { join } from 'path'
import { safeParseStdout } from '@/lib/api-utils'

const ROOT = process.cwd()
const CACHE_FALLBACK = join(ROOT, 'python', 'stoloto_analysis_v3.json')

// ── In-memory cache ───────────────────────────────────────────────
interface CacheEntry {
  data: Record<string, unknown>
  timestamp: number
  hasRealData: boolean  // true if data has actual analysis (score > 0)
}

let _memoryCache: CacheEntry | null = null
let _refreshPromise: Promise<void> | null = null
const MEMORY_CACHE_TTL = 30 * 60 * 1000 // 30 minutes

/** Check if cached data contains real analysis results (not just game list) */
function hasRealAnalysis(data: Record<string, unknown>): boolean {
  const games = data.games as Array<{ score: number }> | undefined
  if (!games || games.length === 0) return false
  return games.some(g => g.score > 0)
}

export async function POST(request: Request) {
  try {
    const url = new URL(request.url)
    const forceRefresh = url.searchParams.get('refresh') === 'true'

    // 1. If we have fresh in-memory cache with real data, return immediately
    if (_memoryCache && !forceRefresh && _memoryCache.hasRealData) {
      const age = Date.now() - _memoryCache.timestamp
      if (age < MEMORY_CACHE_TTL) {
        return NextResponse.json(_memoryCache.data)
      }
    }

    // 2. Check if Python cache file has been updated (newer than in-memory cache)
    const pythonCacheExists = existsSync(CACHE_FALLBACK)
    const pythonCacheNewer = pythonCacheExists && _memoryCache
      ? statSync(CACHE_FALLBACK).mtimeMs > _memoryCache.timestamp
      : false

    // 3. If Python cache file exists and is newer (or we have no real data), load it directly
    if (pythonCacheExists && (forceRefresh || pythonCacheNewer || !_memoryCache?.hasRealData)) {
      const fallback = loadFallbackCache()
      if (fallback && hasRealAnalysis(fallback)) {
        _memoryCache = { data: fallback, timestamp: Date.now(), hasRealData: true }
        // Also trigger background refresh to keep data up-to-date
        triggerBackgroundRefresh()
        return NextResponse.json({ ...fallback, _refreshing: true })
      }
    }

    // 4. Return stale in-memory cache while refreshing in background
    if (_memoryCache && !forceRefresh) {
      triggerBackgroundRefresh()
      return NextResponse.json({ ..._memoryCache.data, _refreshing: true })
    }

    // 5. No in-memory cache — try quick game list from API
    if (existsSync(join(ROOT, 'python', 'analyze.py'))) {
      const quickResult = await getGameListQuick()
      if (quickResult) {
        _memoryCache = { data: quickResult, timestamp: Date.now(), hasRealData: false }
        triggerBackgroundRefresh()
        return NextResponse.json({ ...quickResult, _refreshing: true })
      }
    }

    // 6. Try loading Python cache file as fallback
    if (pythonCacheExists) {
      const fallback = loadFallbackCache()
      if (fallback) {
        _memoryCache = { data: fallback, timestamp: Date.now(), hasRealData: hasRealAnalysis(fallback) }
        triggerBackgroundRefresh()
        return NextResponse.json({ ...fallback, _refreshing: true })
      }
    }

    // 7. Nothing works — return minimal hardcoded response + trigger refresh
    const minimal = getMinimalResponse()
    _memoryCache = { data: minimal, timestamp: Date.now(), hasRealData: false }
    triggerBackgroundRefresh()
    return NextResponse.json({ ...minimal, _refreshing: true })
  } catch (error) {
    // Last resort: try any cache available
    if (_memoryCache) return NextResponse.json(_memoryCache.data)
    const fallback = loadFallbackCache()
    if (fallback) {
      _memoryCache = { data: fallback, timestamp: Date.now(), hasRealData: hasRealAnalysis(fallback) }
      return NextResponse.json(fallback)
    }
    const minimal = getMinimalResponse()
    _memoryCache = { data: minimal, timestamp: Date.now(), hasRealData: false }
    return NextResponse.json(minimal)
  }
}

/** Quick: call analyze.py with --list-only flag to get game names from API (no draw fetching) */
async function getGameListQuick(): Promise<Record<string, unknown> | null> {
  try {
    const { stdout, code } = await runPythonScript('analyze.py', ['--list-only'], {
      timeout: 30000, // 30 seconds — just fetches game list from API
    })

    if (code === 0 && stdout) {
      const parsed = safeParseStdout(stdout)
      if (parsed && !parsed.error && parsed.data) {
        const d = parsed.data
        if (d.games && Array.isArray(d.games) && d.games.length > 0) {
          return d as Record<string, unknown>
        }
      }
    }
  } catch {
    // Timeout or spawn error — fall through
  }
  return null
}

/** Trigger background refresh (fire and forget) */
function triggerBackgroundRefresh() {
  if (_refreshPromise) return // Already refreshing

  _refreshPromise = (async () => {
    try {
      console.log('[api/analyze] Background refresh started...')
      const { stdout, code, stderr } = await runPythonScript('analyze.py', [], {
        timeout: 1800000, // 30 minutes for full background analysis
      })
      if (code === 0 && stdout) {
        const parsed = safeParseStdout(stdout)
        if (parsed && !parsed.error && parsed.data) {
          const d = parsed.data
          if (d.games && Array.isArray(d.games) && d.games.length > 0) {
            _memoryCache = { data: d as Record<string, unknown>, timestamp: Date.now(), hasRealData: hasRealAnalysis(d) }
            console.log(`[api/analyze] Background refresh completed successfully (${(d.games as unknown[]).length} games)`)
          } else {
            console.warn('[api/analyze] Background refresh: no games in output')
          }
        } else {
          console.warn('[api/analyze] Background refresh: invalid output format', parsed?.error)
        }
      } else {
        console.warn('[api/analyze] Background refresh script failed, code:', code)
        if (stderr) console.warn('[api/analyze] stderr:', stderr.slice(-500))
      }
    } catch (e) {
      console.warn('[api/analyze] Background refresh failed:', e instanceof Error ? e.message : e)
    } finally {
      _refreshPromise = null
    }
  })()
}

/** Minimal hardcoded response when no cache exists at all */
function getMinimalResponse() {
  const allGames = [
    '4x20', '6x45plus', '5x36plus', 'keno2', '5x2', '7x49', '5x36',
    '6x45', 'rapido', 'zabegalochka', 'sportloto', '4x20plus',
    '6x49plus', 'zabeg', 'duel', '12x24', 'bingo75', 'djoker',
    '6x36', 'top3', '5x2_2', 'moment', 'xoroshist', 'rk',
    'goldenkey', 'kvartet', 'nards-pro', 'gzhl', 'football-gold',
    '5x36lite', 'dvazhdydva', 'prize', 'goldenkhanka', 'expres',
    'ruslotto', 'architect', 'bingo', 'syndicate',
  ]

  const games = allGames.map(name => ({
    name,
    key: name,
    score: 0,
    verdict: '⏳ Анализ загружается...',
    verdict_color: 'green' as const,
    draws: 0,
    hot_numbers: [] as number[],
    cold_numbers: [] as number[],
    chi2_p: null,
    autocorr: null,
    data_file: '',
    source: 'minimal',
    has_local_data: false,
  }))

  return {
    games,
    high_anomaly: [] as unknown[],
    total_games_analyzed: 0,
    categories: {
      high: [] as unknown[],
      moderate: [] as unknown[],
      normal: [] as unknown[],
      insufficient: games, // All games shown as "loading" in insufficient section
    },
    _refreshing: true,
  }
}

/**
 * Load the Python cache file and convert to frontend format.
 */
function loadFallbackCache(): Record<string, unknown> | null {
  try {
    if (!existsSync(CACHE_FALLBACK)) return null

    const raw = JSON.parse(readFileSync(CACHE_FALLBACK, 'utf-8'))
    if (!Array.isArray(raw) || raw.length === 0) return null

    // Convert raw list to frontend format
    const games = raw.map((r: Record<string, unknown>) => {
      const verdict = String(r.verdict ?? '❓ Мало данных')
      let verdict_color = 'green'
      if (verdict.includes('ВЫСОКАЯ')) verdict_color = 'red'
      else if (verdict.includes('Умеренная')) verdict_color = 'yellow'
      else if (verdict.includes('Статистически') || verdict.includes('случайная')) verdict_color = 'green'

      const top10: [number, number][] = (r.top10 ?? [])
      const cold10: [number, number][] = (r.cold10 ?? [])

      return {
        name: r.name,
        key: r.name,
        score: r.score ?? 0,
        verdict,
        verdict_color,
        draws: r.draws ?? 0,
        hot_numbers: top10.slice(0, 5).map(([n]: [number, number]) => n),
        cold_numbers: cold10.slice(0, 5).map(([n]: [number, number]) => n),
        chi2_p: r.chi2_p ?? null,
        autocorr: r.autocorr ?? null,
        data_file: '',
        source: 'cache',
        has_local_data: false,
        redirect_target: r.redirect_target ?? null,
      }
    }).sort((a, b) => ((b as Record<string, number>).score ?? 0) - ((a as Record<string, number>).score ?? 0))

    const high_anomaly = games.filter((g: Record<string, unknown>) => (g.score as number) >= 50)

    return {
      games,
      high_anomaly,
      total_games_analyzed: games.length,
      categories: {
        high: games.filter((g: Record<string, unknown>) => g.verdict_color === 'red'),
        moderate: games.filter((g: Record<string, unknown>) => g.verdict_color === 'yellow'),
        normal: games.filter((g: Record<string, unknown>) => g.verdict_color === 'green' && (g.draws as number) >= 10),
        insufficient: games.filter((g: Record<string, unknown>) => (g.draws as number) < 10 || String(g.verdict).includes('Мало данных')),
      },
    }
  } catch {
    return null
  }
}
