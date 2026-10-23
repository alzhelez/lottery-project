'use client'
import { useCallback, useEffect, useState } from 'react'
import { BlockBalls } from './Balls'
import { nf, num, pct, plural, pval } from './format'
import type { Info } from './GameView'

interface Entry {
  id: string
  draw_no: number
  source: string
  source_title: string
  detail: string
  made_at: string
  status: 'pending' | 'checked' | 'late' | 'invalid'
  numbers: number[][]
  blocks: Array<{ name: string }>
  actual?: number[][]
  hits?: number
  expected?: number
  won?: number | null
  draw_date?: string
  mechanism?: 'L' | 'R' | null
  ordered?: boolean
  in_place?: number
  in_place_expected?: number
}

interface Summary {
  source: string
  title: string
  checked: number
  pending: number
  late: number
  mean_hits?: number
  expected?: number
  excess_pct?: number
  p_better?: number | null
  won?: number
  money_checked?: number
  ordered_checked?: number
  in_place?: number
  in_place_expected?: number
  spent?: number
  return?: number
  p_sequential?: number | null
}

const SHORT: Record<string, string> = { analysis_best: 'Л', analysis_consensus: 'К', chaos: 'Х', godmode: 'Б' }
const SOURCE_TITLE: Record<string, string> = {
  analysis_best: 'лучший метод', analysis_consensus: 'консенсус', chaos: 'порядок из хаоса', godmode: 'режим Бога',
}
const ORDER = ['chaos', 'analysis_best', 'analysis_consensus', 'godmode']

const STATUS: Record<Entry['status'], string> = {
  pending: 'ждёт тиража',
  checked: 'сверен',
  late: 'после тиража',
  invalid: 'не сверить',
}

export function JournalPanel({ info }: { info: Info }) {
  const [data, setData] = useState<{ entries: Entry[]; summary: Summary[]; byMechanism?: Array<{ mechanism: string; title: string; summary: Summary[] }> } | null>(null)
  const [source, setSource] = useState('all')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const toggle = (no: number) => setExpanded((prev) => {
    const next = new Set(prev)
    if (next.has(no)) next.delete(no)
    else next.add(no)
    return next
  })
  const load = useCallback(async () => {
    const r = await fetch(`/api/games/${info.slug}/journal`, { cache: 'no-store' })
    setData(await r.json())
  }, [info.slug])
  useEffect(() => { load() }, [load])

  if (!data) return null
  const entries = data.entries.filter((e) => source === 'all' || e.source === source)
  // «Все»: одна строка на тираж, прогнозы источников раскрываются по нажатию
  const groups: Array<{ no: number; items: Entry[] }> = []
  const byNo = new Map<number, Entry[]>()
  for (const e of entries) {
    if (!byNo.has(e.draw_no)) {
      byNo.set(e.draw_no, [])
      groups.push({ no: e.draw_no, items: byNo.get(e.draw_no)! })
    }
    byNo.get(e.draw_no)!.push(e)
  }
  for (const g of groups) g.items.sort((a, b) => (ORDER.indexOf(a.source) + 9) % 9 - (ORDER.indexOf(b.source) + 9) % 9)
  const lastNo = info.last?.no ?? 0

  return (
    <section className="panel" data-testid="journal">
      <p>
        Каждый прогноз на следующий тираж (анализ и режим Бога) записывается сюда до тиража, а после загрузки
        новых тиражей сверяется с результатом. Это проверка без подгонки: модель не видела тиража, на котором
        её оценивают. Прогнозы, сделанные по устаревшим данным уже после тиража, помечаются «после тиража»
        и в итог не входят.
      </p>

      {data.summary.length === 0 ? (
        <p className="empty">Журнал пуст. Запустите анализ или режим Бога — прогноз на тираж №{info.nextNo} попадёт сюда.</p>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data" data-testid="journal-summary">
              <thead>
                <tr>
                  <th>Источник</th><th className="r">Сверено</th><th className="r">Ждут</th>
                  <th className="r">Угадано в среднем</th><th className="r">Случайный выбор</th>
                  <th className="r">Разница</th><th className="r">p</th><th className="r" title="По реальным выплатам тиражей">Выиграно, ₽</th>
                  <th className="r" title="Числа прогноза на той же позиции, что в тираже (порядок выпадения)">На своём месте</th>
                </tr>
              </thead>
              <tbody>
                {data.summary.map((s) => (
                  <tr key={s.source}>
                    <td>{s.title}{s.late > 0 && <span className="sub">не засчитано (после тиража): {s.late}</span>}</td>
                    <td className="r num">{s.checked}</td>
                    <td className="r num">{s.pending}</td>
                    <td className="r num">{num(s.mean_hits)}</td>
                    <td className="r num">{num(s.expected)}</td>
                    <td className="r num">{pct(s.excess_pct)}</td>
                    <td className="r num">{s.p_better == null && s.checked > 0 ? <span className="muted" title="p считается от 30 сверенных прогнозов">мало данных</span> : pval(s.p_better)}</td>
                    <td className="r num">{s.won != null ? `${nf.format(Math.round(s.won))} (${s.money_checked})` : '—'}
                      {s.return != null && <span className="sub">потрачено {nf.format(Math.round(s.spent ?? 0))}, возврат {num(s.return, 2)}</span>}</td>
                    <td className="r num">{s.in_place != null ? <>{s.in_place}<span className="sub">ожидалось {num(s.in_place_expected, 1)}</span></> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            p — вероятность, что случайный выбор угадал бы столько же или больше. Считается от 30 сверенных
            прогнозов: на меньшем числе разница почти всегда объясняется удачей. Сводка по всем играм — на странице
            «Итоги прогнозов». Числа прогноза записываются в
            предсказанном порядке выпадения; «на своём месте» — сколько из них вышли именно на той позиции.
          </p>
          {(data.byMechanism?.length ?? 0) > 0 && (
            <div className="table-wrap">
              <table className="data compact" data-testid="journal-by-mechanism">
                <thead><tr><th>Способ розыгрыша</th><th>Источник</th><th className="r">Сверено</th><th className="r">Угадано</th><th className="r">Случайный выбор</th><th className="r">Разница</th><th className="r">p</th></tr></thead>
                <tbody>
                  {data.byMechanism!.flatMap((m) => m.summary.filter((s) => s.checked > 0).map((s) => (
                    <tr key={m.mechanism + s.source}>
                      <td>{m.title}</td><td>{s.title}</td><td className="r num">{s.checked}</td>
                      <td className="r num">{num(s.mean_hits)}</td><td className="r num">{num(s.expected)}</td>
                      <td className="r num">{pct(s.excess_pct)}</td>
                      <td className="r num">{s.p_better == null ? <span className="muted">мало данных</span> : pval(s.p_better)}</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </div>
          )}

          <div className="run-bar">
            {[['all', 'Все'], ...data.summary.map((s) => [s.source, s.title])].map(([k, label]) => (
              <button key={k} className={`chip ${source === k ? 'on' : ''}`} onClick={() => setSource(k)}>{label}</button>
            ))}
          </div>

          <div className="table-wrap">
            {source === 'all' ? (
              <table className="data" data-testid="journal-entries">
                <thead>
                  <tr><th>Тираж</th><th>Прогнозы</th><th>Выпало</th><th className="r">Угадано по источникам</th><th className="r">Ожидалось</th><th className="r">Выигрыш, ₽</th><th>Статус</th></tr>
                </thead>
                <tbody>
                  {groups.slice(0, 200).flatMap((g) => {
                    const open = expanded.has(g.no)
                    const head = g.items[0]
                    const actual = g.items.find((e) => e.actual)?.actual
                    const won = g.items.reduce((acc, e) => (e.won != null ? (acc ?? 0) + e.won : acc), null as number | null)
                    const status = g.items.some((e) => e.status === 'pending') ? 'pending'
                      : g.items.some((e) => e.status === 'checked') ? 'checked' : head.status
                    const rows = [
                      <tr key={`g${g.no}`} className="group-row" data-testid="journal-draw" aria-expanded={open}
                        onClick={() => toggle(g.no)}>
                        <td>
                          <span className="caret">{open ? '▾' : '▸'}</span> №{g.no}
                          {head.mechanism && <span className="sub">{head.mechanism === 'L' ? 'лототрон' : 'ГСЧ'}</span>}
                          {head.draw_date && <span className="sub">тираж {head.draw_date}</span>}
                        </td>
                        <td>{g.items.length} {plural(g.items.length, 'источник', 'источника', 'источников')}
                          <span className="sub">{g.items.map((e) => e.source_title).join(', ')}</span></td>
                        <td>{actual ? <BlockBalls blocks={actual} tone="actual" size="sm" /> : <span className="muted">—</span>}</td>
                        <td className="r num">
                          {g.items.map((e) => (
                            <span key={e.id} className="hit-chip" title={e.source_title}>{SHORT[e.source] ?? e.source_title.slice(0, 1)} {e.hits ?? '—'}</span>
                          ))}
                        </td>
                        <td className="r num">{head.expected != null ? num(head.expected, 2) : '—'}</td>
                        <td className="r num">{won != null ? nf.format(won) : '—'}</td>
                        <td><span className={`status-tag st-${status}`}>{STATUS[status]}</span></td>
                      </tr>,
                    ]
                    if (open) {
                      for (const e of g.items) {
                        rows.push(
                          <tr key={e.id} className="sub-row" data-testid="journal-source-row">
                            <td><span className="sub">прогноз {e.made_at.replace('T', ' ').slice(0, 16)}</span></td>
                            <td>{e.source_title}{e.detail && <span className="sub">{e.detail}</span>}</td>
                            <td><BlockBalls blocks={e.numbers} actual={e.actual} size="sm" />
                              {e.in_place != null && <span className="sub">на своём месте: {e.in_place}</span>}</td>
                            <td className="r num">{e.hits ?? '—'}</td>
                            <td className="r num">{e.expected != null ? num(e.expected, 2) : '—'}</td>
                            <td className="r num">{e.won != null ? nf.format(e.won) : '—'}</td>
                            <td>
                              <span className={`status-tag st-${e.status}`}>{STATUS[e.status]}</span>
                              {e.status === 'pending' && lastNo >= e.draw_no && <span className="sub">тиража нет в архиве</span>}
                            </td>
                          </tr>,
                        )
                      }
                    }
                    return rows
                  })}
                </tbody>
              </table>
            ) : (
              <table className="data" data-testid="journal-entries">
                <thead>
                  <tr><th>Тираж</th><th>Источник</th><th>Прогноз</th><th>Выпало</th><th className="r">Угадано</th><th className="r">Ожидалось</th><th className="r">Выигрыш, ₽</th><th>Статус</th></tr>
                </thead>
                <tbody>
                  {entries.slice(0, 200).map((e) => (
                    <tr key={e.id}>
                      <td>№{e.draw_no}{e.mechanism && <span className="sub">{e.mechanism === 'L' ? 'лототрон' : 'ГСЧ'}</span>}<span className="sub">прогноз {e.made_at.replace('T', ' ').slice(0, 16)}</span></td>
                      <td>{e.source_title}{e.detail && <span className="sub">{e.detail}</span>}</td>
                      <td><BlockBalls blocks={e.numbers} actual={e.actual} size="sm" /></td>
                      <td>{e.actual ? <BlockBalls blocks={e.actual} tone="actual" size="sm" /> : <span className="muted">—</span>}</td>
                      <td className="r num">{e.hits ?? '—'}</td>
                      <td className="r num">{e.expected != null ? num(e.expected, 2) : '—'}</td>
                      <td className="r num">{e.won != null ? nf.format(e.won) : '—'}</td>
                      <td>
                        <span className={`status-tag st-${e.status}`}>{STATUS[e.status]}</span>
                        {e.status === 'pending' && lastNo >= e.draw_no && <span className="sub">тиража нет в архиве</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {source === 'all' && groups.length > 0 && (
            <p className="muted small">Нажмите на тираж, чтобы увидеть прогноз каждого источника. Угадано: {Object.entries(SHORT).map(([k, v]) => `${v} — ${SOURCE_TITLE[k]}`).join(', ')}.</p>
          )}
        </>
      )}
    </section>
  )
}
