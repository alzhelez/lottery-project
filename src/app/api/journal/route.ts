import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { gameTitle, isExcluded, readJournal, readJson } from '@/lib/games'
import { cumulative, type JournalEntry, SOURCES, summarize } from '@/lib/journalStats'
import { dataDir, resultsFile } from '@/lib/paths'

export const dynamic = 'force-dynamic'

/** Итоги журнала по всем играм: по источникам, по играм, накопленное превышение. */
export async function GET() {
  let files: string[] = []
  try {
    // убранные игры (excluded в config/games.json) в итоги не входят
    files = fs.readdirSync(path.join(dataDir(), 'journal')).filter((f) => f.endsWith('.json') && !isExcluded(f.slice(0, -5)))
  } catch {
    files = []
  }
  const nextdraw = readJson<{ games: Record<string, { usual_return?: number | null }> }>(resultsFile(null, 'nextdraw.json'))
  const all: JournalEntry[] = []
  const games = files.map((f) => {
    const slug = f.slice(0, -5)
    const entries = ((readJournal(slug)?.entries ?? []) as unknown as JournalEntry[])
    all.push(...entries)
    return { slug, title: gameTitle(slug), summary: summarize(entries), usual_return: nextdraw?.games?.[slug]?.usual_return ?? null }
  }).filter((g) => g.summary.some((s) => Number(s.checked) > 0))
  const curves = Object.entries(SOURCES).map(([source, title]) => ({ source, title, ...cumulative(all.filter((e) => e.source === source)) }))
    .filter((c) => c.n > 0)
  return NextResponse.json({ summary: summarize(all), games, curves })
}
