import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { gameTitle, isExcluded, readJournal } from '@/lib/games'
import { bestWorst, halfSummary, type StatEntry, thresholdLabel } from '@/lib/halfStats'
import { dataDir } from '@/lib/paths'

export const dynamic = 'force-dynamic'

/** Статистика по играм: сколько раз каждый метод журнала угадал не меньше половины своих чисел,
 * сколько дал бы случайный выбор, лучший и худший метод игры. */
export async function GET() {
  let files: string[] = []
  try {
    files = fs.readdirSync(path.join(dataDir(), 'journal')).filter((f) => f.endsWith('.json') && !isExcluded(f.slice(0, -5)))
  } catch {
    files = []
  }
  const games = files.map((f) => {
    const slug = f.slice(0, -5)
    const entries = ((readJournal(slug)?.entries ?? []) as unknown as StatEntry[])
    const checked = entries.filter((e) => e.status === 'checked')
    const rows = halfSummary(checked)
    return { slug, title: gameTitle(slug), threshold: thresholdLabel(checked), rows, ...bestWorst(rows) }
  }).filter((g) => g.rows.length > 0)
    .sort((a, b) => a.title.localeCompare(b.title, 'ru'))
  return NextResponse.json({ games })
}
