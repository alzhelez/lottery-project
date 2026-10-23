import { NextResponse } from 'next/server'
import { readJournal } from '@/lib/games'
import { type JournalEntry as Entry, summarize } from '@/lib/journalStats'
import { isValidSlug } from '@/lib/paths'

export const dynamic = 'force-dynamic'

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
