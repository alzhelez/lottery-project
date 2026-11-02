/**
 * Статистика «угадал половину чисел и больше» по журналу прогнозов: сколько раз каждый источник
 * (метод) угадал не меньше половины своих чисел, сколько таких раз дал бы случайный выбор того
 * же размера, лучший и худший метод игры.
 */
import { erfc, type JournalEntry, LOWER, MIN_FOR_P, SOURCES } from './journalStats'

export interface StatEntry extends JournalEntry {
  numbers?: number[][]
  actual?: number[][]
  blocks?: Array<{ lo: number; hi: number }>
}

const LOG_FACT: number[] = [0]
function logFact(n: number): number {
  for (let i = LOG_FACT.length; i <= n; i++) LOG_FACT.push(LOG_FACT[i - 1] + Math.log(i))
  return LOG_FACT[n]
}
function logComb(n: number, k: number): number {
  return k < 0 || k > n ? -Infinity : logFact(n) - logFact(k) - logFact(n - k)
}

/** Распределение числа совпадений: n случайных чисел из N против K выпавших (гипергеометрическое). */
export function hypergeomPmf(N: number, K: number, n: number): number[] {
  const out: number[] = []
  for (let k = 0; k <= Math.min(K, n); k++) out.push(Math.exp(logComb(K, k) + logComb(N - K, n - k) - logComb(N, n)))
  return out
}

function convolve(a: number[], b: number[]): number[] {
  const out = new Array(a.length + b.length - 1).fill(0)
  a.forEach((x, i) => b.forEach((y, j) => { out[i + j] += x * y }))
  return out
}

/** Сколько чисел в прогнозе (по всем полям). */
export function pickedCount(e: StatEntry): number {
  return (e.numbers ?? []).reduce((s, b) => s + b.length, 0)
}

/** «Половина и больше»: из 6 — от 3, из 8 — от 4, из 5 — от 3. */
export function halfThreshold(total: number): number {
  return Math.ceil(total / 2)
}

/** Шанс, что случайный выбор того же размера угадает не меньше половины чисел; null — не посчитать. */
export function chanceHalf(e: StatEntry): number | null {
  const total = pickedCount(e)
  if (!total || !e.blocks || !e.actual || e.blocks.length !== e.numbers?.length) return null
  let dist = [1]
  for (let i = 0; i < e.blocks.length; i++) {
    const N = e.blocks[i].hi - e.blocks[i].lo + 1
    const K = e.actual[i]?.length ?? 0
    const n = e.numbers[i].length
    if (N <= 0 || K > N || n > N) return null
    dist = convolve(dist, hypergeomPmf(N, K, n))
  }
  return Math.min(1, dist.slice(halfThreshold(total)).reduce((s, p) => s + p, 0))
}

export interface HalfRow {
  source: string
  title: string
  goal?: 'fewer'
  checked: number
  half: number              // сколько раз угадано не меньше половины
  share: number | null      // half / checked
  expected: number          // столько раз в среднем дал бы случайный выбор
  expected_share: number | null
  p_better: number | null   // шанс получить столько же или больше случайно (при ≥ MIN_FOR_P прогнозах)
}

export function halfSummary(entries: StatEntry[]): HalfRow[] {
  return Object.entries(SOURCES).flatMap(([source, title]) => {
    const done = entries.filter((e) => e.source === source && e.status === 'checked' && pickedCount(e) > 0)
    if (!done.length) return []
    let half = 0
    let expected = 0
    let variance = 0
    for (const e of done) {
      if ((e.hits ?? 0) >= halfThreshold(pickedCount(e))) half++
      const p = chanceHalf(e) ?? 0
      expected += p
      variance += p * (1 - p)
    }
    // нормальное приближение с поправкой на непрерывность; на малом числе прогнозов p не даём
    const z = variance > 0 ? (half - 0.5 - expected) / Math.sqrt(variance) : 0
    const row: HalfRow = {
      source, title, checked: done.length, half,
      share: half / done.length, expected, expected_share: expected / done.length,
      p_better: done.length >= MIN_FOR_P && variance > 0 ? 0.5 * erfc(z / Math.SQRT2) : null,
    }
    if (LOWER.has(source)) row.goal = 'fewer'
    return [row]
  })
}

/** Самый частый порог игры, например «от 3 из 6». */
export function thresholdLabel(entries: StatEntry[]): string | null {
  const counts = new Map<number, number>()
  for (const e of entries) {
    const t = pickedCount(e)
    if (t) counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  if (!counts.size) return null
  const total = [...counts.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0][0]
  return `от ${halfThreshold(total)} из ${total}`
}

/** Лучший и худший метод игры по доле прогнозов, угадавших не меньше половины. «Наименее
 * вероятные» не участвуют: у них цель обратная. При равной доле выше тот, у кого больше прогнозов. */
export function bestWorst(rows: HalfRow[]): { best: HalfRow | null; worst: HalfRow | null; tie: boolean } {
  const ranked = rows.filter((r) => !r.goal && r.checked > 0)
    .sort((a, b) => (b.share ?? 0) - (a.share ?? 0) || b.checked - a.checked)
  if (!ranked.length) return { best: null, worst: null, tie: false }
  const best = ranked[0]
  const worst = ranked.length > 1 ? ranked[ranked.length - 1] : null
  return { best, worst, tie: worst != null && best.share === worst.share }
}
