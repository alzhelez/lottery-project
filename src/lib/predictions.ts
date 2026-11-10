/**
 * Прогнозы игры по тиражам: журнал + анализ за период (data/journal_retro); на тираж у метода
 * одна запись, журнальная — если она есть. Отсюда:
 *  - coverage — у всех ли тиражей периода есть сверенные предсказания каждого метода;
 *  - digital — выгрузка «в цифровом виде»: по методу строка из тиражей, в тираже на каждое число
 *    прогноза 1 (выпало) или 0 (нет), поля через «/».
 */
import fs from 'node:fs'
import path from 'node:path'
import { readJson } from './games'
import { dataDir, drawsFile } from './paths'

/** Методы, которые сейчас пишут прогнозы, и их сокращения для выгрузки. */
export const METHODS: Array<{ source: string; short: string; title: string }> = [
  { source: 'final', short: 'ФП', title: 'Финальное предсказание' },
  { source: 'analysis_best', short: 'ЛМА', title: 'Лучший метод анализа' },
  { source: 'analysis_consensus', short: 'КМ', title: 'Консенсус методов' },
  { source: 'chaos', short: 'ПиХ', title: 'Порядок из хаоса' },
  { source: 'godmode', short: 'РБ', title: 'Режим Бога' },
  { source: 'golden', short: 'ЗС', title: 'Золотая середина' },
  { source: 'least', short: 'НВ', title: 'Наименее вероятные' },
]

export interface PEntry {
  source: string; draw_no: number; status: string; numbers: number[][]; actual?: number[][]
  draw_date?: string; checked_at?: string; retro?: boolean
}

function parseDate(s: string | undefined): number {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})(?: (\d{2}):(\d{2}))?/.exec(s ?? '')
  return m ? new Date(+m[3], +m[2] - 1, +m[1], +(m[4] ?? 0), +(m[5] ?? 0)).getTime() : 0
}

/** Сыгранные тиражи игры из архива: номер и время, по возрастанию номера. */
export function drawList(slug: string): Array<{ no: number; time: number }> {
  let text = ''
  try {
    text = fs.readFileSync(drawsFile(slug), 'utf-8')
  } catch {
    return []
  }
  const out: Array<{ no: number; time: number }> = []
  for (const line of text.split('\n')) {
    const parts = line.split('||')
    const no = Number(parts[1])
    if (parts.length >= 3 && Number.isInteger(no)) out.push({ no, time: parseDate(parts[0]) })
  }
  return out.sort((a, b) => a.no - b.no)
}

/** Сверенные прогнозы игры: «метод:тираж» → запись (журнал перекрывает анализ за период). */
export function checkedEntries(slug: string): Map<string, PEntry> {
  const by = new Map<string, PEntry>()
  for (const dir of ['journal_retro', 'journal']) {
    const j = readJson<{ entries?: PEntry[] }>(path.join(dataDir(), dir, `${slug}.json`))
    for (const e of j?.entries ?? []) if (e.status === 'checked') by.set(`${e.source}:${e.draw_no}`, e)
  }
  return by
}

/** Период анализа, дней: тот, за который в последний раз считалось доверие (по умолчанию 7). */
export function analysisDays(): number {
  const t = readJson<{ days?: number }>(path.join(dataDir(), 'trust.json'))
  return [1, 3, 7, 14, 30].includes(Number(t?.days)) ? Number(t?.days) : 7
}

export interface Coverage {
  days: number; draws: number; first_no: number | null; last_no: number | null; complete: boolean
  methods: Array<{ source: string; short: string; title: string; have: number; missing: number }>
  missing_total: number
}

/** Автоанализ: у каждого ли тиража последних days дней есть сверенное предсказание каждого метода. */
export function coverage(slug: string, days = analysisDays(), now = Date.now()): Coverage {
  const since = now - days * 86_400_000
  const draws = drawList(slug).filter((d) => d.time >= since)
  const by = checkedEntries(slug)
  const methods = METHODS.map((m) => {
    const have = draws.filter((d) => by.has(`${m.source}:${d.no}`)).length
    return { ...m, have, missing: draws.length - have }
  })
  const missing = methods.reduce((a, m) => a + m.missing, 0)
  return {
    days, draws: draws.length, first_no: draws[0]?.no ?? null, last_no: draws.at(-1)?.no ?? null,
    complete: draws.length > 0 && missing === 0, methods, missing_total: missing,
  }
}

/** Прогноз тиража «в цифровом виде»: на каждое число прогноза (по возрастанию) — 1, если оно
 * выпало в своём поле, иначе 0; поля — через «/». «1,6,12,14|1,4,14,15» при выпавших 1 и 15 →
 * «1000/0001». */
export function digitalCode(e: PEntry): string {
  return e.numbers.map((block, b) => {
    const drawn = new Set(e.actual?.[b] ?? [])
    return [...block].sort((x, y) => x - y).map((n) => (drawn.has(n) ? '1' : '0')).join('')
  }).join('/')
}

/** Текст выгрузки: строка на метод, тиражи от самого дальнего к ближайшему через «;».
 * days = 0 — все тиражи, по которым есть хотя бы одно сверенное предсказание. */
export function digitalExport(slug: string, title: string, days: number, now = Date.now()): string {
  const by = checkedEntries(slug)
  const times = new Map(drawList(slug).map((d) => [d.no, d.time]))
  const since = days > 0 ? now - days * 86_400_000 : 0
  // время тиража — из архива; если тиража там нет, из самой записи
  const entryTime = new Map<number, number>()
  for (const e of by.values()) if (!entryTime.has(e.draw_no)) entryTime.set(e.draw_no, parseDate(e.draw_date))
  const nos = [...entryTime.keys()].filter((no) => (times.get(no) ?? entryTime.get(no) ?? 0) >= since).sort((a, b) => a - b)
  const period = days > 0 ? `за ${days} дн.` : 'за всё время'
  const lines = [
    `# ${title} — прогнозы в цифровом виде ${period}`,
    '# Строка — метод; тиражи от самого дальнего к ближайшему через «;».',
    '# В тираже на каждое число прогноза (по возрастанию): 1 — число выпало, 0 — нет; поля через «/»; «-» — прогноза нет.',
    '# У «НВ» (наименее вероятные) 1 тоже значит «выпало» — для них чем меньше единиц, тем лучше.',
    '# Сокращения: ' + METHODS.map((m) => `${m.short} — ${m.title}`).join(', ') + '.',
    `Тиражи: ${nos.join('; ')}`,
  ]
  for (const m of METHODS) {
    const cells = nos.map((no) => { const e = by.get(`${m.source}:${no}`); return e ? digitalCode(e) : '-' })
    if (cells.some((c) => c !== '-')) lines.push(`${m.short}: ${cells.join('; ')}`)
  }
  return lines.join('\n') + '\n'
}
