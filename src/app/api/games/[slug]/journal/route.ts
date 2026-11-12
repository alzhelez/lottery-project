import { NextResponse } from 'next/server'
import path from 'node:path'
import { readJournal, readJson } from '@/lib/games'
import { type JournalEntry as Entry, summarize } from '@/lib/journalStats'
import { dataDir, isValidSlug } from '@/lib/paths'
import { analysisDays, drawList, historyEntries } from '@/lib/predictions'

export const dynamic = 'force-dynamic'

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  const journal = readJournal(slug)
  const real = ((journal?.entries ?? []) as unknown as Entry[]).slice()
  // Прогнозы, восстановленные задним числом — только по тиражам до каждого тиража: «анализ за период»
  // (data/journal_retro) и история прогнозов (data/history — её дополняет каждый цикл автозапуска,
  // поэтому в ней есть и тиражи, сыгранные после анализа). В список они попадают там, где сверенной
  // записи журнала на этот тираж у метода нет, — с пометкой retro; итоги по источникам выше считаются
  // только по настоящему журналу. Вся история (весь архив) — в выгрузке «в цифровом виде».
  const have = new Set(real.filter((e) => e.status === 'checked').map((e) => `${e.source}:${e.draw_no}`))
  const retro = (readJson<{ entries?: Entry[] }>(path.join(dataDir(), 'journal_retro', `${slug}.json`))?.entries ?? [])
    .filter((e) => e.status === 'checked' && !have.has(`${e.source}:${e.draw_no}`))
    .map((e) => ({ ...e, retro: true }))
  for (const e of retro) have.add(`${e.source}:${e.draw_no}`)
  // история — с начала периода анализа (не раньше: у быстрых игр в ней десятки тысяч тиражей)
  const retroSince = retro.reduce((m, e) => Math.min(m, e.draw_no), Infinity)
  const sinceTime = Date.now() - analysisDays() * 86_400_000
  const fromNo = Math.min(retroSince, drawList(slug).find((d) => d.time >= sinceTime)?.no ?? Infinity)
  retro.push(...(historyEntries(slug, fromNo, have) as unknown as Array<Entry & { retro: boolean }>))
  const order = (a: Entry, b: Entry) => b.draw_no - a.draw_no || b.made_at.localeCompare(a.made_at)
  const entries = real.sort(order)
  const all = [...real, ...retro].sort(order)
  // отдельно для тиражей на лототроне и ГСЧ (если в журнале есть оба)
  const byMechanism = (['L', 'R'] as const)
    .map((m) => ({ mechanism: m, title: m === 'L' ? 'Лототрон' : 'ГСЧ', summary: summarize(entries.filter((e) => e.mechanism === m)) }))
    .filter((x) => x.summary.length > 0)
  return NextResponse.json({
    entries: all, summary: summarize(entries), byMechanism: byMechanism.length > 1 ? byMechanism : [],
    counts: { journal: real.length, retro: retro.length },
  })
}
