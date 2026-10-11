import fs from 'node:fs'
import path from 'node:path'
import registry from '../../config/games.json'
import { dataDir, drawsFile, isValidSlug, resultsFile } from './paths'

export interface Activity {
  active: boolean
  daysSinceLast: number | null   // дней от последнего тиража до последней проверки архива
  checkedAt: string | null       // когда архив игры последний раз проверялся загрузчиком
  dataAgeDays: number | null     // сколько дней назад была эта проверка
  threshold: number
}

export interface GameInfo {
  slug: string
  title: string
  stolotoUrl: string
  draws: number
  first: { no: number; date: string } | null
  last: { no: number; date: string } | null
  nextNo: number | null
  missing: number
  activity: Activity
}

interface RegistryGame { slug: string; title: string }

const REGISTRY = new Map<string, RegistryGame>((registry.games as RegistryGame[]).map((g) => [g.slug, g]))
const INACTIVE_DAYS = Number(process.env.LOTTERY_INACTIVE_DAYS || (registry as { inactive_days?: number }).inactive_days || 15)
const DAY = 86_400_000

function parseDrawDate(s: string): Date | null {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?/.exec(s)
  return m ? new Date(+m[3], +m[2] - 1, +m[1], +(m[4] ?? 0), +(m[5] ?? 0)) : null
}

function readMeta(slug: string): { checked_at?: string } {
  return readJson(drawsFile(slug).replace(/\.txt$/, '.meta.json')) ?? {}
}

/** Игра активна, если последний тираж не старше INACTIVE_DAYS дней на момент последней
 *  проверки архива (если архив не проверялся — на текущий момент). Та же логика, что в Python. */
export function computeActivity(lastDate: string | null, checkedAt: string | null, now = new Date()): Activity {
  const checked = checkedAt ? new Date(checkedAt) : null
  const ref = checked && !Number.isNaN(checked.getTime()) ? checked : now
  const last = lastDate ? parseDrawDate(lastDate) : null
  const round = (v: number) => Math.round(v * 10) / 10
  return {
    active: last ? (ref.getTime() - last.getTime()) / DAY <= INACTIVE_DAYS : false,
    daysSinceLast: last ? round((ref.getTime() - last.getTime()) / DAY) : null,
    checkedAt: checkedAt ?? null,
    dataAgeDays: round((now.getTime() - ref.getTime()) / DAY),
    threshold: INACTIVE_DAYS,
  }
}

/** Активные игры из последнего ответа API (data/api_games.json, пишет загрузчик). */
function apiGames(): Array<{ name: string; title: string | null }> | null {
  const raw = readJson<{ games: Array<{ name: string; title: string | null }> }>(path.join(dataDir(), 'api_games.json'))
  return raw?.games ?? null
}

export function gameTitle(slug: string): string {
  return REGISTRY.get(slug)?.title ?? apiGames()?.find((g) => g.name === slug)?.title ?? slug
}

export function stolotoUrl(slug: string): string {
  return `https://www.stoloto.ru/${slug}/game/`
}

/** Быстрое чтение сводки по файлу тиражей (номера, даты) без разбора чисел. */
export function readGameInfo(slug: string): GameInfo | null {
  if (!isValidSlug(slug)) return null
  const file = drawsFile(slug)
  const checkedAt = readMeta(slug).checked_at ?? null
  const base: GameInfo = {
    slug, title: gameTitle(slug), stolotoUrl: stolotoUrl(slug),
    draws: 0, first: null, last: null, nextNo: null, missing: 0,
    activity: computeActivity(null, checkedAt),
  }
  if (!fs.existsSync(file)) return REGISTRY.has(slug) || apiGames()?.some((g) => g.name === slug) ? base : null
  const seen = new Map<number, string>()
  for (const line of fs.readFileSync(file, 'utf-8').split('\n')) {
    const parts = line.trim().split('||')
    if (parts.length < 3 || !parts.slice(2).some((p) => p.trim())) continue
    const no = Number.parseInt(parts[1], 10)
    if (Number.isFinite(no) && !seen.has(no)) seen.set(no, parts[0].trim())
  }
  if (seen.size === 0) return base
  const nos = [...seen.keys()].sort((a, b) => a - b)
  const first = nos[0]
  const last = nos[nos.length - 1]
  return {
    ...base,
    draws: nos.length,
    first: { no: first, date: seen.get(first)! },
    last: { no: last, date: seen.get(last)! },
    nextNo: last + 1,
    missing: last - first + 1 - nos.length,
    activity: computeActivity(seen.get(last)!, checkedAt),
  }
}

/** Игры, для которых есть файл тиражей, плюс все игры реестра. */
export function listGames(): GameInfo[] {
  // если API уже сообщило список активных игр — показываем его, а не весь реестр
  const api = apiGames()
  const slugs = new Set<string>(api ? api.map((g) => g.name).filter(isValidSlug) : REGISTRY.keys())
  const dir = path.join(dataDir(), 'draws')
  if (fs.existsSync(dir)) {
    for (const f of fs.readdirSync(dir)) {
      const m = /^draws_(.+)\.txt$/.exec(f)
      if (m && isValidSlug(m[1])) slugs.add(m[1])
    }
  }
  return [...slugs].map((s) => readGameInfo(s)).filter((g): g is GameInfo => g !== null)
}

export function readJson<T = unknown>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8')) as T
  } catch {
    return null
  }
}

export function readResult(slug: string, kind: 'analysis' | 'godmode') {
  return readJson(resultsFile(slug, `${kind}.json`))
}

export function readJournal(slug: string) {
  return readJson<{ entries: Array<Record<string, unknown>> }>(path.join(dataDir(), 'journal', `${slug}.json`))
}

export function readScan() {
  return readJson<{ generated_at: string; games: Array<Record<string, unknown>> }>(resultsFile(null, 'scan.json'))
}
