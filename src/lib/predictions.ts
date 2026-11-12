/**
 * Прогнозы игры по тиражам: журнал, анализ за период (data/journal_retro) и история прогнозов на
 * весь архив (data/history, python/lottery/history.py); на тираж у метода один прогноз, журнальный —
 * если он есть. Отсюда:
 *  - coverage — у всех ли тиражей архива есть предсказания каждого метода;
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
export function drawList(slug: string): Array<{ no: number; time: number; date: string }> {
  let text = ''
  try {
    text = fs.readFileSync(drawsFile(slug), 'utf-8')
  } catch {
    return []
  }
  const out: Array<{ no: number; time: number; date: string }> = []
  for (const line of text.split('\n')) {
    const parts = line.split('||')
    const no = Number(parts[1])
    if (parts.length >= 3 && Number.isInteger(no)) out.push({ no, time: parseDate(parts[0]), date: parts[0] })
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

const HISTORY_VERSION = 1

interface History {
  version: number; first_no: number | null; last_no: number
  blocks?: Array<{ lo: number; hi: number }>
  draws: { nos: number[]; actual: string[] }
  sources: Record<string, { detail?: string; nos: number[]; numbers: string[] }>
}

/** История прогнозов на весь архив; null — ещё не посчитана (или посчитана старой версией). */
export function readHistory(slug: string): History | null {
  const h = readJson<History>(path.join(dataDir(), 'history', `${slug}.json`))
  return h && h.version === HISTORY_VERSION && h.sources && h.draws ? h : null
}

const dec = (text: string): number[][] => text.split('|').map((b) => b.split(',').filter(Boolean).map(Number))

/** Код «1000/0001» из чисел строкой «1,6,12,14|1,4,14,15» и выпавших — без разбора в объекты
 * (у быстрых игр в истории десятки тысяч тиражей). */
function codeOf(numbers: string, actual: string): string {
  const act = actual.split('|')
  return numbers.split('|').map((block, b) => {
    const drawn = new Set((act[b] ?? '').split(','))
    return block.split(',').filter(Boolean).map(Number).sort((x, y) => x - y).map((n) => (drawn.has(String(n)) ? '1' : '0')).join('')
  }).join('/')
}

/** Прогнозы истории на тиражи с номера fromNo в виде записей журнала (сверенные, с пометкой
 * retro) — для вкладки «Журнал прогнозов»: там, где на тираж у метода нет ни записи журнала, ни
 * анализа за период (skip — «метод:тираж», которые уже есть). */
export function historyEntries(slug: string, fromNo: number, skip: Set<string>): Array<Record<string, unknown>> {
  const h = readHistory(slug)
  if (!h) return []
  const actual = new Map(h.draws.nos.map((no, i) => [no, h.draws.actual[i]]))
  const dates = new Map(drawList(slug).map((d) => [d.no, d.date]))
  const titles = new Map(METHODS.map((m) => [m.source, m.title]))
  const out: Array<Record<string, unknown>> = []
  for (const [source, v] of Object.entries(h.sources)) {
    v.nos.forEach((no, i) => {
      const act = actual.get(no)
      if (no < fromNo || act == null || skip.has(`${source}:${no}`)) return
      const numbers = dec(v.numbers[i])
      const drawn = dec(act)
      let hits = 0, expected = 0
      numbers.forEach((block, b) => {
        const a = new Set(drawn[b] ?? [])
        hits += block.filter((n) => a.has(n)).length
        const spec = h.blocks?.[b]
        if (spec) expected += (block.length * a.size) / (spec.hi - spec.lo + 1)
      })
      out.push({
        id: `h-${source}-${no}`, source, source_title: titles.get(source) ?? source, detail: v.detail ?? '',
        draw_no: no, draw_date: dates.get(no), made_at: '', numbers, actual: drawn, hits,
        ...(h.blocks ? { expected } : {}), status: 'checked', retro: true,
      })
    })
  }
  return out
}

export interface Coverage {
  built: boolean              // история прогнозов на весь архив посчитана
  days: number                // период «анализа за период» — с ним запускается пересчёт
  draws: number; first_no: number | null; last_no: number | null
  with_predictions: number    // тиражей, у которых есть предсказание хотя бы одного метода
  complete: boolean
  /** have — тиражей с предсказанием, missing — пропуски, na — тиражи, где предсказания быть не
   * может (разгон; первая часть архива у «Режима Бога» и «Порядка из хаоса»); restored — из have
   * посчитаны задним числом, а не записаны в журнал до тиража. have + missing + na = draws. */
  methods: Array<{ source: string; short: string; title: string; have: number; missing: number; na: number; restored: number }>
  missing_total: number
  restored_total: number
}

/** Считают каждый тираж истории; у остальных («Режим Бога», «Порядок из хаоса») честный прогноз
 * есть только на части архива, поэтому «дырой» внутри истории их отсутствие не считается. */
const ALWAYS = new Set(['final', 'analysis_best', 'analysis_consensus', 'golden', 'least'])

/** Автоанализ: у каждого ли тиража архива есть предсказание каждого метода. Пропуск — тираж, на
 * который метод мог дать прогноз, а его нет: новый тираж, ещё не попавший в историю, или «дыра» у
 * методов анализа внутри истории. То же считает бот (python/lottery/coverage.py). */
export function coverage(slug: string): Coverage {
  const nos = drawList(slug).map((d) => d.no)
  const h = readHistory(slug)
  const checked = checkedEntries(slug)
  const have = new Map<string, Set<number>>()
  const recorded = new Map<string, Set<number>>()      // записаны в журнал до тиража
  for (const e of checked.values()) {
    if (!have.has(e.source)) { have.set(e.source, new Set()); recorded.set(e.source, new Set()) }
    have.get(e.source)!.add(e.draw_no)
    if (!e.retro) recorded.get(e.source)!.add(e.draw_no)
  }
  for (const [s, v] of Object.entries(h?.sources ?? {})) {
    if (!have.has(s)) { have.set(s, new Set()); recorded.set(s, new Set()) }
    const set = have.get(s)!
    for (const no of v.nos) set.add(no)
  }
  const last = h?.last_no ?? Infinity
  const first = h?.first_no ?? 0
  const covered = new Set<number>()
  const methods = METHODS.map((m) => {
    const got = have.get(m.source) ?? new Set<number>()
    const rec = recorded.get(m.source) ?? new Set<number>()
    const inHistory = h != null && m.source in h.sources
    let n = 0, missing = 0, restored = 0
    for (const no of nos) {
      if (got.has(no)) {
        n++
        covered.add(no)
        if (!rec.has(no)) restored++
      } else if (inHistory && (no > last || (ALWAYS.has(m.source) && no >= first))) missing++
    }
    return { ...m, have: n, missing, na: nos.length - n - missing, restored }
  })
  const missing = methods.reduce((a, m) => a + m.missing, 0)
  return {
    built: h != null, days: analysisDays(), draws: nos.length, first_no: nos[0] ?? null, last_no: nos.at(-1) ?? null,
    with_predictions: covered.size, complete: h != null && nos.length > 0 && missing === 0, methods,
    missing_total: missing, restored_total: methods.reduce((a, m) => a + m.restored, 0),
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
 * days = 0 — все тиражи архива, по которым есть хотя бы одно предсказание (история на весь архив +
 * журнал); иначе — тиражи последних days дней. */
export function digitalExport(slug: string, title: string, days: number, now = Date.now()): string {
  const by = checkedEntries(slug)
  const h = readHistory(slug)
  const times = new Map(drawList(slug).map((d) => [d.no, d.time]))
  const since = days > 0 ? now - days * 86_400_000 : 0
  // время тиража — из архива; если тиража там нет, из самой записи
  const entryTime = new Map<number, number>()
  for (const e of by.values()) if (!entryTime.has(e.draw_no)) entryTime.set(e.draw_no, parseDate(e.draw_date))
  const inPeriod = (no: number) => (times.get(no) ?? entryTime.get(no) ?? 0) >= since
  // код по «метод:тираж»: история, поверх неё — анализ за период и журнал
  const codes = new Map<string, string>()
  const all = new Set<number>()
  if (h) {
    const actual = new Map(h.draws.nos.map((no, i) => [no, h.draws.actual[i]]))
    for (const [s, v] of Object.entries(h.sources)) {
      v.nos.forEach((no, i) => {
        const act = actual.get(no)
        if (act == null || !inPeriod(no)) return
        codes.set(`${s}:${no}`, codeOf(v.numbers[i], act))
        all.add(no)
      })
    }
  }
  for (const [key, e] of by) {
    if (!inPeriod(e.draw_no)) continue
    codes.set(key, digitalCode(e))
    all.add(e.draw_no)
  }
  const nos = [...all].sort((a, b) => a - b)
  const period = days > 0 ? `за ${days} дн.` : 'все тиражи архива'
  const lines = [
    `# ${title} — прогнозы в цифровом виде: ${period}`,
    '# Строка — метод; тиражи от самого дальнего к ближайшему через «;».',
    '# В тираже на каждое число прогноза (по возрастанию): 1 — число выпало, 0 — нет; поля через «/»; «-» — прогноза нет.',
    '# У «НВ» (наименее вероятные) 1 тоже значит «выпало» — для них чем меньше единиц, тем лучше.',
    '# Сокращения: ' + METHODS.map((m) => `${m.short} — ${m.title}`).join(', ') + '.',
    ...(days === 0 && !h ? ['# Предсказания на весь архив ещё не посчитаны — здесь только журнал и анализ за период. Нажмите «Пересчитать предсказания» на вкладке «Обзор».'] : []),
    `Тиражи: ${nos.join('; ')}`,
  ]
  for (const m of METHODS) {
    const cells = nos.map((no) => codes.get(`${m.source}:${no}`) ?? '-')
    if (cells.some((c) => c !== '-')) lines.push(`${m.short}: ${cells.join('; ')}`)
  }
  return lines.join('\n') + '\n'
}
