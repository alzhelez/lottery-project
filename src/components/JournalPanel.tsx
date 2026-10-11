'use client'
import { useCallback, useEffect, useState } from 'react'
import { BlockBalls } from './Balls'
import { nf, num, pct, pval } from './format'
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
}

const STATUS: Record<Entry['status'], string> = {
  pending: 'ждёт тиража',
  checked: 'сверен',
  late: 'после тиража',
  invalid: 'не сверить',
}

export function JournalPanel({ info }: { info: Info }) {
  const [data, setData] = useState<{ entries: Entry[]; summary: Summary[] } | null>(null)
  const [source, setSource] = useState('all')
  const load = useCallback(async () => {
    const r = await fetch(`/api/games/${info.slug}/journal`, { cache: 'no-store' })
    setData(await r.json())
  }, [info.slug])
  useEffect(() => { load() }, [load])

  if (!data) return null
  const entries = data.entries.filter((e) => source === 'all' || e.source === source)
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
                    <td className="r num">{s.won != null ? `${nf.format(Math.round(s.won))} (${s.money_checked})` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            p — вероятность, что случайный выбор угадал бы столько же или больше. Считается от 30 сверенных
            прогнозов: на меньшем числе разница почти всегда объясняется удачей.
          </p>

          <div className="run-bar">
            {[['all', 'Все'], ...data.summary.map((s) => [s.source, s.title])].map(([k, label]) => (
              <button key={k} className={`chip ${source === k ? 'on' : ''}`} onClick={() => setSource(k)}>{label}</button>
            ))}
          </div>

          <div className="table-wrap">
            <table className="data" data-testid="journal-entries">
              <thead>
                <tr><th>Тираж</th><th>Источник</th><th>Прогноз</th><th>Выпало</th><th className="r">Угадано</th><th className="r">Ожидалось</th><th className="r">Выигрыш, ₽</th><th>Статус</th></tr>
              </thead>
              <tbody>
                {entries.slice(0, 200).map((e) => (
                  <tr key={e.id}>
                    <td>№{e.draw_no}<span className="sub">прогноз {e.made_at.replace('T', ' ').slice(0, 16)}</span></td>
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
          </div>
        </>
      )}
    </section>
  )
}
