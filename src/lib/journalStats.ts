/** Итоги журнала прогнозов: общие для страницы игры и сводки по всем играм. */

export const MIN_FOR_P = 30

export const SOURCES: Record<string, string> = {
  analysis_best: 'Лучший метод анализа',
  analysis_consensus: 'Консенсус методов',
  chaos: 'Порядок из хаоса',
  godmode: 'Режим Бога',
}

export interface JournalEntry {
  source: string
  status: string
  hits?: number
  expected?: number
  variance?: number
  draw_no: number
  made_at: string
  checked_at?: string
  won?: number | null
  spent?: number | null
  mechanism?: 'L' | 'R' | null
  in_place?: number
  in_place_expected?: number
}

/** Дополнительная функция ошибок (Abramowitz–Stegun 7.1.26, точность ~1e-7). */
export function erfc(x: number): number {
  const z = Math.abs(x)
  const t = 1 / (1 + 0.5 * z)
  const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 +
    t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))))
  return x >= 0 ? r : 2 - r
}

/**
 * «Всегда верное» p-value последовательной проверки (смесь Роббинса): его можно смотреть
 * после каждого тиража сколько угодно раз, и ложная тревога всё равно не чаще заявленного.
 * Обычное p при постоянном подсматривании рано или поздно опустится ниже 0,05 даже у
 * случайного выбора. S — сумма (угадано − ожидалось), V — её дисперсия, rho — настройка на
 * преимущество порядка нескольких процентов (≈ 1/дисперсия 500 прогнозов).
 */
export function alwaysValidP(S: number, V: number, rho: number): number {
  if (V <= 0 || rho <= 0) return 1
  const logLambda = -0.5 * Math.log(1 + rho * V) + (rho * S * S) / (2 * (1 + rho * V))
  // только преимущество над случайным выбором
  if (S <= 0) return 1
  return Math.min(1, Math.exp(-logLambda))
}

export function summarize(entries: JournalEntry[]) {
  return Object.entries(SOURCES).flatMap(([source, title]) => {
    const own = entries.filter((e) => e.source === source)
    if (own.length === 0) return []
    const done = own.filter((e) => e.status === 'checked')
    const row: Record<string, unknown> = {
      source, title, checked: done.length,
      pending: own.filter((e) => e.status === 'pending').length,
      late: own.filter((e) => e.status === 'late').length,
    }
    if (done.length) {
      const hits = done.reduce((s, e) => s + (e.hits ?? 0), 0)
      const exp = done.reduce((s, e) => s + (e.expected ?? 0), 0)
      const vr = done.reduce((s, e) => s + (e.variance ?? 0), 0)
      const z = vr > 0 ? (hits - exp) / Math.sqrt(vr) : 0
      Object.assign(row, {
        hits, expected_total: exp,
        mean_hits: hits / done.length,
        expected: exp / done.length,
        excess_pct: exp ? ((hits - exp) / exp) * 100 : 0,
        z,
        // на малом числе прогнозов нормальное приближение врёт, а сам результат — шум
        p_better: done.length >= MIN_FOR_P ? 0.5 * erfc(z / Math.SQRT2) : null,
        p_sequential: done.length >= MIN_FOR_P ? alwaysValidP(hits - exp, vr, 1 / (500 * (vr / done.length))) : null,
      })
      const ordered = done.filter((e) => e.in_place != null)
      if (ordered.length) {
        Object.assign(row, {
          ordered_checked: ordered.length,
          in_place: ordered.reduce((s, e) => s + (e.in_place ?? 0), 0),
          in_place_expected: ordered.reduce((s, e) => s + (e.in_place_expected ?? 0), 0),
        })
      }
      const paid = done.filter((e) => e.won != null)
      if (paid.length) {
        Object.assign(row, { money_checked: paid.length, won: paid.reduce((s, e) => s + (e.won ?? 0), 0) })
        const priced = paid.filter((e) => e.spent)
        const spent = priced.reduce((s, e) => s + (e.spent ?? 0), 0)
        if (spent > 0) {
          const wonPriced = priced.reduce((s, e) => s + (e.won ?? 0), 0)
          Object.assign(row, { spent, won_priced: wonPriced, return: wonPriced / spent })
        }
      }
    }
    return [row]
  })
}

/** Накопленное (угадано − ожидалось) по порядку сверки и граница ±2σ — для графика. */
export function cumulative(entries: JournalEntry[], points = 160) {
  const done = entries.filter((e) => e.status === 'checked')
    .sort((a, b) => (a.checked_at ?? a.made_at).localeCompare(b.checked_at ?? b.made_at) || a.draw_no - b.draw_no)
  let s = 0
  let v = 0
  const ex: number[] = [0]
  const band: number[] = [0]
  for (const e of done) {
    s += (e.hits ?? 0) - (e.expected ?? 0)
    v += e.variance ?? 0
    ex.push(s)
    band.push(2 * Math.sqrt(v))
  }
  const step = Math.max(1, Math.ceil(ex.length / points))
  const pick = (a: number[]) => a.filter((_, i) => i % step === 0 || i === a.length - 1).map((x) => Math.round(x * 10) / 10)
  return { n: done.length, excess: pick(ex), upper: pick(band), lower: pick(band.map((b) => -b)) }
}
