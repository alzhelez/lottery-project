import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { gameTitle, isExcluded, readJournal, readJson } from '@/lib/games'
import { bestWorst, gameMetric, halfSummary, heterogeneity, type StatEntry, thresholdLabel, watchList } from '@/lib/halfStats'
import { SOURCES } from '@/lib/journalStats'
import { dataDir } from '@/lib/paths'

export const dynamic = 'force-dynamic'

function slugsIn(dir: string): string[] {
  try {
    return fs.readdirSync(dir).filter((f) => f.endsWith('.json') && f !== 'status.json' && !isExcluded(f.slice(0, -5)))
      .map((f) => f.slice(0, -5))
  } catch {
    return []
  }
}

// журналы быстрых игр — мегабайты: итог по файлу пересчитывается, только когда файл изменился
const cache = new Map<string, { mtime: number; stats: ReturnType<typeof gameStats> }>()

function cachedStats(file: string, slug: string, read: () => StatEntry[]) {
  let mtime = 0
  try {
    mtime = fs.statSync(file).mtimeMs
  } catch {
    return null
  }
  const hit = cache.get(file)
  if (hit && hit.mtime === mtime) return hit.stats
  const stats = gameStats(slug, read())
  cache.set(file, { mtime, stats })
  return stats
}

function gameStats(slug: string, entries: StatEntry[]) {
  const checked = entries.filter((e) => e.status === 'checked')
  const rows = halfSummary(checked)
  const metric = gameMetric(checked)
  return {
    slug, title: gameTitle(slug), metric, threshold: thresholdLabel(checked), rows,
    ...bestWorst(rows, metric), heterogeneity: heterogeneity(rows),
  }
}

/** Время тиража записи журнала: «дд.мм.гггг чч:мм» из draw_date, иначе время сверки. */
function entryTime(e: StatEntry & { draw_date?: string; checked_at?: string }): number {
  const m = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})/.exec(e.draw_date ?? '')
  if (m) return new Date(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]).getTime()
  return e.checked_at ? new Date(e.checked_at).getTime() : 0
}

const periodCache = new Map<string, { key: string; stats: ReturnType<typeof gameStats> }>()

/** «По методам» за период анализа — те же данные, что у рейтинга доверия (trust.py): анализ за
 * период + настоящие прогнозы журнала с того же времени; на тираж у метода одна запись,
 * журнальная — если есть. */
function periodStats(slug: string, since: number) {
  const files = [path.join(dataDir(), 'journal_retro', `${slug}.json`), path.join(dataDir(), 'journal', `${slug}.json`)]
  const key = files.map((f) => { try { return fs.statSync(f).mtimeMs } catch { return 0 } }).join(':') + ':' + since
  const hit = periodCache.get(slug)
  if (hit && hit.key === key) return hit.stats
  const byKey = new Map<string, StatEntry>()
  for (const f of files) {                        // журнал — вторым: перекрывает запись анализа
    for (const e of readJson<{ entries?: StatEntry[] }>(f)?.entries ?? []) {
      if (e.status === 'checked' && entryTime(e) >= since) byKey.set(`${e.source}:${e.draw_no}`, e)
    }
  }
  const stats = gameStats(slug, [...byKey.values()])
  periodCache.set(slug, { key, stats })
  return stats
}

/** Статистика по играм: сколько раз каждый метод журнала угадал не меньше половины своих чисел
 * (в «Топ-3» — среднее угаданных), сколько дал бы случайный выбор, лучший и худший метод игры,
 * отличаются ли методы больше случайного, пары «Под наблюдением» и та же статистика по
 * ретро-проверке за неделю (data/journal_retro, отдельно от настоящего журнала). */
export async function GET() {
  const journalDir = path.join(dataDir(), 'journal')
  const games = slugsIn(journalDir)
    .map((slug) => cachedStats(path.join(journalDir, `${slug}.json`), slug,
      () => (readJournal(slug)?.entries ?? []) as unknown as StatEntry[]))
    .filter((g): g is NonNullable<typeof g> => g != null && g.rows.length > 0)
    .sort((a, b) => a.title.localeCompare(b.title, 'ru'))
  const retroDir = path.join(dataDir(), 'journal_retro')
  const status = readJson<Record<string, unknown>>(path.join(retroDir, 'status.json'))
  const retroGames = slugsIn(retroDir)
    .map((slug) => cachedStats(path.join(retroDir, `${slug}.json`), slug,
      () => readJson<{ entries?: StatEntry[] }>(path.join(retroDir, `${slug}.json`))?.entries ?? []))
    .filter((g): g is NonNullable<typeof g> => g != null && g.rows.length > 0)
    .sort((a, b) => a.title.localeCompare(b.title, 'ru'))
  // доверие к методам (python/lottery/trust.py): рейтинг источников в каждой игре за период
  const trustRaw = readJson<{ made_at?: string; days?: number; since?: string
    games?: Record<string, { sources: Record<string, Record<string, unknown>>; ranking: string[] }> }>(path.join(dataDir(), 'trust.json'))
  const trust = trustRaw?.games ? {
    made_at: trustRaw.made_at, days: trustRaw.days, since: trustRaw.since,
    games: Object.entries(trustRaw.games).filter(([slug]) => !isExcluded(slug)).map(([slug, g]) => ({
      slug, title: gameTitle(slug),
      rows: g.ranking.map((source) => ({ source, title: SOURCES[source] ?? source, ...g.sources[source] })),
    })).sort((a, b) => a.title.localeCompare(b.title, 'ru')),
  } : null
  const since = trustRaw?.since ? new Date(trustRaw.since).getTime() : null
  const period = since == null ? null : {
    days: trustRaw?.days, since: trustRaw?.since,
    games: [...new Set([...slugsIn(journalDir), ...slugsIn(retroDir)])].map((slug) => periodStats(slug, since))
      .filter((g) => g.rows.length > 0).sort((a, b) => a.title.localeCompare(b.title, 'ru')),
  }
  return NextResponse.json({
    games,
    trust,
    period,
    watch: watchList(games),
    retro: {
      status: status ? { status: status.status, started_at: status.started_at, finished_at: status.finished_at,
        days: status.days, since: status.since } : null,
      games: retroGames,
      watch: watchList(retroGames),
    },
  })
}
