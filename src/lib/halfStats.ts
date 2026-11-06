/**
 * Статистика «угадал половину чисел и больше» по журналу прогнозов: сколько раз каждый источник
 * (метод) угадал не меньше половины своих чисел, сколько таких раз дал бы случайный выбор того
 * же размера, лучший и худший метод игры.
 */
import { erfc, type JournalEntry, LOWER, MIN_FOR_P, SOURCES } from './journalStats'

export interface StatEntry extends JournalEntry {
  numbers?: number[][]
  actual?: number[][]
  blocks?: Array<{ lo: number; hi: number; mode?: string }>
}

/** Как считать игру: «половина и больше» или среднее угаданных. Если случайный выбор угадывает
 * половину своих чисел реже чем в 1% прогнозов (в «Топ-3» прогноз — по цифре на каждую из 12
 * позиций, и 6 из 12 случайно выходит ≈0,1%), столбец почти всегда 0 — там сравнивается среднее
 * число угаданных с ожиданием случайного выбора. */
export type Metric = 'half' | 'mean'

export const MEAN_METRIC_BELOW = 0.01

export function gameMetric(entries: StatEntry[]): Metric {
  const sample = entries.slice(-300).map(chanceHalf).filter((p): p is number => p != null)
  if (!sample.length) return 'half'
  return sample.reduce((a, p) => a + p, 0) / sample.length < MEAN_METRIC_BELOW ? 'mean' : 'half'
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
  half_variance: number     // дисперсия числа таких раз у случайного выбора
  p_better: number | null   // шанс получить столько же или больше случайно (при ≥ MIN_FOR_P прогнозах)
  // среднее угаданных против случайного выбора (для «Топ-3» и для «Под наблюдением»)
  mean_hits: number
  mean_expected: number
  excess_pct: number
  hits_diff: number         // Σ(угадано − ожидалось)
  hits_variance: number
  z: number
  p_mean: number | null     // одностороннее p по среднему (для «наименее вероятных» — в сторону «меньше»)
  halves: [number | null, number | null]   // превышение, % — на первой и второй половине прогнозов по времени
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
    const H = done.reduce((a, e) => a + (e.hits ?? 0), 0)
    const E = done.reduce((a, e) => a + (e.expected ?? 0), 0)
    const V = done.reduce((a, e) => a + (e.variance ?? 0), 0)
    const zm = V > 0 ? (H - E) / Math.sqrt(V) : 0
    const sign = LOWER.has(source) ? -1 : 1
    const byTime = [...done].sort((a, b) => a.draw_no - b.draw_no)
    const mid = Math.floor(byTime.length / 2)
    const pct = (part: StatEntry[]) => {
      const e = part.reduce((a, x) => a + (x.expected ?? 0), 0)
      return part.length && e ? (100 * (part.reduce((a, x) => a + (x.hits ?? 0), 0) - e)) / e : null
    }
    const row: HalfRow = {
      source, title, checked: done.length, half,
      share: half / done.length, expected, expected_share: expected / done.length, half_variance: variance,
      p_better: done.length >= MIN_FOR_P && variance > 0 ? 0.5 * erfc(z / Math.SQRT2) : null,
      mean_hits: H / done.length, mean_expected: E / done.length, excess_pct: E ? (100 * (H - E)) / E : 0,
      hits_diff: H - E, hits_variance: V, z: zm,
      p_mean: done.length >= MIN_FOR_P && V > 0 ? 0.5 * erfc((sign * zm) / Math.SQRT2) : null,
      halves: [pct(byTime.slice(0, mid)), pct(byTime.slice(mid))],
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

/** Лучший и худший метод игры: по доле прогнозов, угадавших не меньше половины (metric 'half'),
 * или по превышению среднего угаданных над случайным выбором ('mean'). «Наименее вероятные» не
 * участвуют: у них цель обратная. При равенстве выше тот, у кого больше прогнозов. */
export function bestWorst(rows: HalfRow[], metric: Metric = 'half'): { best: HalfRow | null; worst: HalfRow | null; tie: boolean } {
  const value = (r: HalfRow) => (metric === 'half' ? r.share ?? 0 : r.excess_pct)
  const ranked = rows.filter((r) => !r.goal && r.checked > 0)
    .sort((a, b) => value(b) - value(a) || b.checked - a.checked)
  if (!ranked.length) return { best: null, worst: null, tie: false }
  const best = ranked[0]
  const worst = ranked.length > 1 ? ranked[ranked.length - 1] : null
  return { best, worst, tie: worst != null && value(best) === value(worst) }
}

/** Шанс, что хи-квадрат с df степенями свободы не меньше q (приближение Уилсона–Хилферти;
 * для df ≥ 2 погрешность — сотые доли). */
export function chi2Sf(q: number, df: number): number {
  if (df <= 0) return 1
  if (q <= 0) return 1
  const a = 2 / (9 * df)
  const z = (Math.cbrt(q / df) - (1 - a)) / Math.sqrt(a)
  return 0.5 * erfc(z / Math.SQRT2)
}

export interface Heterogeneity { q: number; df: number; p: number; differ: boolean }

/** Отличаются ли методы игры между собой больше, чем бывает случайно (Q Кокрана: разброс
 * «угадано − ожидалось» между методами против их дисперсий). Считается по среднему числу
 * угаданных — число раз «половина и больше» на сотне прогнозов слишком мало для такой проверки —
 * и только по методам от MIN_FOR_P прогнозов (null — таких меньше двух). Методы прогнозируют
 * одни и те же тиражи и часто берут похожие числа, поэтому «разница случайна» — скорее мягко. */
export function heterogeneity(rows: HalfRow[]): Heterogeneity | null {
  const parts = rows.filter((r) => !r.goal && r.checked >= MIN_FOR_P)
    .map((r) => ({ d: r.hits_diff, v: r.hits_variance })).filter((x) => x.v > 0)
  if (parts.length < 2) return null
  const sv = parts.reduce((a, x) => a + x.v, 0)
  const sd = parts.reduce((a, x) => a + x.d, 0)
  const q = Math.max(0, parts.reduce((a, x) => a + (x.d * x.d) / x.v, 0) - (sd * sd) / sv)
  const df = parts.length - 1
  const p = chi2Sf(q, df)
  return { q, df, p, differ: p < 0.05 }
}

export interface WatchItem {
  slug: string; title: string; source: string; source_title: string; goal?: 'fewer'
  checked: number; excess_pct: number; p: number; p_holm: number; halves: [number | null, number | null]
  holds: boolean
}

/** «Под наблюдением»: пары «игра × метод» с устойчивым перевесом — среднее угаданных лучше
 * случайного с p < 0,05 (у «наименее вероятных» — реже), от MIN_FOR_P прогнозов. holds — перевес
 * есть в обеих половинах прогнозов по времени. p_holm — с поправкой Холма на все проверенные
 * пары: только она говорит, не удача ли это. */
export function watchList(games: Array<{ slug: string; title: string; rows: HalfRow[] }>): WatchItem[] {
  const tested = games.flatMap((g) => g.rows.filter((r) => r.p_mean != null).map((r) => ({ g, r })))
  const m = tested.length
  const sorted = [...tested].sort((a, b) => (a.r.p_mean ?? 1) - (b.r.p_mean ?? 1))
  const holm = new Map<HalfRow, number>()
  let run = 0
  sorted.forEach(({ r }, i) => { run = Math.max(run, Math.min(1, (m - i) * (r.p_mean ?? 1))); holm.set(r, run) })
  return sorted.filter(({ r }) => (r.p_mean ?? 1) < 0.05).map(({ g, r }) => {
    const good = (x: number | null) => x != null && (r.goal ? x < 0 : x > 0)
    return {
      slug: g.slug, title: g.title, source: r.source, source_title: r.title, goal: r.goal,
      checked: r.checked, excess_pct: r.excess_pct, p: r.p_mean ?? 1, p_holm: holm.get(r) ?? 1,
      halves: r.halves, holds: good(r.halves[0]) && good(r.halves[1]),
    }
  })
}
