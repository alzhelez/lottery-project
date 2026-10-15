import { NextResponse } from 'next/server'
import { readJournal } from '@/lib/games'
import { isValidSlug } from '@/lib/paths'

export const dynamic = 'force-dynamic'

const MIN_FOR_P = 30

const SOURCES: Record<string, string> = {
  analysis_best: 'Лучший метод анализа',
  analysis_consensus: 'Консенсус методов',
  godmode: 'Режим Бога',
}

interface Entry {
  source: string
  status: string
  hits?: number
  expected?: number
  variance?: number
  draw_no: number
  made_at: string
  won?: number | null
  mechanism?: 'L' | 'R' | null
}

/** Сводка по журналу: средние угаданные против ожидания случайного выбора (z-тест). */
function summarize(entries: Entry[]) {
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
        mean_hits: hits / done.length,
        expected: exp / done.length,
        excess_pct: exp ? ((hits - exp) / exp) * 100 : 0,
        z,
        // на малом числе прогнозов нормальное приближение врёт, а сам результат — шум
        p_better: done.length >= MIN_FOR_P ? 0.5 * erfc(z / Math.SQRT2) : null,
      })
      const paid = done.filter((e) => e.won != null)
      if (paid.length) Object.assign(row, { money_checked: paid.length, won: paid.reduce((s, e) => s + (e.won ?? 0), 0) })
    }
    return [row]
  })
}

/** Дополнительная функция ошибок (Abramowitz–Stegun 7.1.26, точность ~1e-7). */
function erfc(x: number): number {
  const z = Math.abs(x)
  const t = 1 / (1 + 0.5 * z)
  const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 +
    t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))))
  return x >= 0 ? r : 2 - r
}

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  const journal = readJournal(slug)
  const entries = ((journal?.entries ?? []) as unknown as Entry[])
    .slice()
    .sort((a, b) => b.draw_no - a.draw_no || b.made_at.localeCompare(a.made_at))
  // отдельно для тиражей на лототроне и ГСЧ (если в журнале есть оба)
  const byMechanism = (['L', 'R'] as const)
    .map((m) => ({ mechanism: m, title: m === 'L' ? 'Лототрон' : 'ГСЧ', summary: summarize(entries.filter((e) => e.mechanism === m)) }))
    .filter((x) => x.summary.length > 0)
  return NextResponse.json({ entries, summary: summarize(entries), byMechanism: byMechanism.length > 1 ? byMechanism : [] })
}
