import path from 'node:path'
import { NextResponse } from 'next/server'
import { readGameInfo, readJournal, readJson, readResult } from '@/lib/games'
import { type JournalEntry, SOURCES, summarize } from '@/lib/journalStats'
import { dataDir, isValidSlug } from '@/lib/paths'

export const dynamic = 'force-dynamic'

type Entry = JournalEntry & { numbers: number[][]; detail?: string; source_title?: string; id: string }
const ORDER = ['analysis_best', 'analysis_consensus', 'chaos', 'godmode', 'experiment']

/**
 * Ближайший тираж игры: прогнозы всех источников, записанные в журнал на этот тираж (те же
 * числа, что будут сверены), время тиража для таймера, итог каждого источника по журналу и
 * наименее вероятные числа.
 */
export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  const info = readGameInfo(slug)
  if (!info) return NextResponse.json({ error: 'Игра не найдена' }, { status: 404 })
  const entries = ((readJournal(slug)?.entries ?? []) as unknown as Entry[])
  const analysis = readResult(slug, 'analysis') as Record<string, any> | null
  const godmode = readResult(slug, 'godmode') as Record<string, any> | null
  const rules = readJson<Record<string, any>>(path.join(dataDir(), 'rules', `${slug}.json`))
  const ev = analysis?.evaluation ?? {}
  const lastNo = info.last?.no ?? 0

  // тираж — тот, на который записано больше всего источников (при равенстве — более поздний):
  // у быстрых игр режим Бога может писать прогноз на тираж позже, чем анализ
  const pending = entries.filter((e) => e.status === 'pending' && e.draw_no > lastNo)
  const bySources = new Map<number, Set<string>>()
  for (const e of pending) {
    if (!bySources.has(e.draw_no)) bySources.set(e.draw_no, new Set())
    bySources.get(e.draw_no)!.add(e.source)
  }
  const ranked = [...bySources.entries()].sort((a, b) => b[1].size - a[1].size || b[0] - a[0])
  const drawNo: number | null = ranked.length ? ranked[0][0] : ev.target?.no ?? null
  if (drawNo == null) {
    return NextResponse.json({ draw_no: null, active: info.activity.active, draws: info.draws, sources: [], least: null })
  }
  const nd = rules?.next_draw
  const date: string | null = ev.target?.no === drawNo && ev.target?.date ? ev.target.date
    : nd?.number === drawNo && nd?.date ? nd.date : null
  const latest = (source: string) => pending.filter((e) => e.source === source && e.draw_no === drawNo)
    .sort((a, b) => b.made_at.localeCompare(a.made_at))[0]

  const record = Object.fromEntries(summarize(entries).map((r) => [r.source as string, r]))
  const sources = ORDER.map((source) => {
    const e = latest(source)
    let numbers = e?.numbers ?? null
    let detail = e?.detail ?? ''
    // журнал пишется только для активной игры — иначе показываем прогноз из последнего анализа
    if (!numbers && ev.target?.no === drawNo) {
      if (source === 'analysis_best') { numbers = ev.next_prediction?.numbers ?? null; detail = ev.next_prediction?.model ?? '' }
      if (source === 'analysis_consensus') numbers = ev.next_consensus ?? null
      if (source === 'chaos' && analysis?.chaos?.next?.draw_no === drawNo) { numbers = analysis.chaos.next.numbers; detail = analysis.chaos.next.model ?? '' }
      if (source === 'godmode' && godmode?.next?.no === drawNo) { numbers = godmode.next.numbers; detail = godmode.next.strategy ?? '' }
      if (source === 'experiment') numbers = ev.next_experiment ?? null
    }
    return { source, title: SOURCES[source], detail, numbers, made_at: e?.made_at ?? null, record: record[source] ?? null }
  }).filter((s) => s.numbers)

  const le = latest('least')
  const least = ev.least?.status === 'ok' || le ? {
    numbers: le?.numbers ?? (ev.target?.no === drawNo ? ev.least?.next_prediction?.numbers : null) ?? null,
    model: le?.detail ?? ev.least?.next_prediction?.model ?? '',
    consensus: ev.target?.no === drawNo ? ev.least?.next_consensus ?? null : null,
    conclusion: ev.least?.conclusion ?? null,
    record: record.least ?? null,
  } : null

  return NextResponse.json({
    draw_no: drawNo, date, how: ev.target?.no === drawNo ? ev.target?.how ?? null : null,
    last_no: lastNo, active: info.activity.active, analysis_at: analysis?.generated_at ?? null,
    super_prize: nd?.number === drawNo ? nd?.super_prize ?? null : null,
    sources, least,
  })
}
