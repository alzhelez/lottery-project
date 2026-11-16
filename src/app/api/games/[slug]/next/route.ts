import path from 'node:path'
import { NextResponse } from 'next/server'
import { readGameInfo, readJournal, readJson, readResult } from '@/lib/games'
import { type JournalEntry, SOURCES, summarize } from '@/lib/journalStats'
import { dataDir, isValidSlug } from '@/lib/paths'

export const dynamic = 'force-dynamic'

type Entry = JournalEntry & { numbers: number[][]; detail?: string; source_title?: string; id: string }
// активные методы; «наименее вероятные» — отдельным блоком
const ORDER = ['final', 'analysis_consensus', 'godmode']
// архивные: показываются, только если их запускали («Запустить архивные методы») и прогноз на тираж есть
const ARCHIVE = ['analysis_best', 'golden', 'chaos']
// версия 2 тех же методов — отдельным блоком; сравнение с первой — в «Статистике»
const V2 = ['final_v2', 'consensus_v2', 'godmode_v2', 'least_v2']

interface Rarity {
  applicable?: boolean; reason?: string; based_on?: number
  draws?: Record<string, Record<string, { score: number; flags: string[] }>>
  rare?: { numbers: number[][]; notes: string[] }
}

/** Числа, которые есть в прогнозе каждого метода (по полям): для подсветки в «Обзоре». Нужны хотя
 * бы два метода — у одного «общими» были бы все его числа. */
function commonNumbers(all: number[][][]): number[][] {
  if (all.length < 2) return []
  return all[0].map((block, b) => block.filter((n) => all.every((numbers) => numbers[b]?.includes(n))).sort((x, y) => x - y))
}

/**
 * Ближайший тираж игры: прогнозы активных методов, записанные в журнал на этот тираж (те же
 * числа, что будут сверены), время тиража для таймера, итог каждого метода по журналу, наименее
 * вероятные числа; common — числа, общие для всех активных методов (кроме наименее вероятных);
 * rarity — пометки популярности и «редкая комбинация» (python/lottery/rarity.py); archive —
 * прогнозы архивных методов, если их запускали.
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

  // тираж — тот, на который записано больше всего источников (при равенстве — ближайший):
  // прогноз пишется на все тиражи до следующего цикла, а режим Бога у быстрых игр может начинать
  // с более позднего тиража
  const pending = entries.filter((e) => e.status === 'pending' && e.draw_no > lastNo)
  const bySources = new Map<number, Set<string>>()
  for (const e of pending) {
    if (!bySources.has(e.draw_no)) bySources.set(e.draw_no, new Set())
    bySources.get(e.draw_no)!.add(e.source)
  }
  const ranked = [...bySources.entries()].sort((a, b) => b[1].size - a[1].size || a[0] - b[0])
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
  // ожидаемый возврат ближайшего тиража и его место в истории наблюдений (python/lottery/nextdraw.py)
  const money = readJson<{ games?: Record<string, Record<string, any>> }>(path.join(dataDir(), 'results', 'nextdraw.json'))?.games?.[slug]
  const rarity = readJson<Rarity>(path.join(dataDir(), 'results', slug, 'rarity.json'))
  const rated = rarity?.based_on === lastNo ? rarity.draws?.[String(drawNo)] ?? {} : {}
  const row = (source: string, fallback: boolean) => {
    const e = latest(source)
    let numbers = e?.numbers ?? null
    let detail = e?.detail ?? ''
    // журнал пишется только для активной игры — иначе показываем прогноз из последнего анализа
    if (fallback && !numbers && ev.target?.no === drawNo) {
      if (source === 'analysis_consensus') numbers = ev.next_consensus ?? null
      if (source === 'godmode' && godmode?.next?.no === drawNo) { numbers = godmode.next.numbers; detail = godmode.next.strategy ?? '' }
    }
    return { source, title: SOURCES[source], detail, numbers, made_at: e?.made_at ?? null, record: record[source] ?? null,
      rarity: e ? rated[source] ?? null : null }
  }
  const sources = ORDER.map((s) => row(s, true)).filter((s) => s.numbers)
  const archive = ARCHIVE.map((s) => row(s, false)).filter((s) => s.numbers)
  const v2 = V2.map((s) => row(s, false)).filter((s) => s.numbers)
  // «Ф» строится из остальных методов: пока сам метод один, «общими» оказались бы все его числа
  const common = sources.filter((s) => s.source !== 'final').length >= 2
    ? commonNumbers(sources.map((s) => s.numbers as number[][])) : []

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
    money: money && money.number === drawNo ? {
      return: money.return, usual_return: money.usual_return ?? null, price: money.price ?? null,
      peak: money.peak ?? null,
    } : null,
    sources, least, common, archive, v2,
    archive_titles: ARCHIVE.map((s) => SOURCES[s]),
    rare: rarity?.based_on === lastNo && rarity.applicable ? rarity.rare ?? null : null,
  })
}
