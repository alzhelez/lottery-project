'use client'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { LineChart } from './Charts'
import { nf, num, pct, plural, pval } from './format'

interface Row {
  source: string; title: string; checked: number; pending: number; late: number
  hits?: number; expected_total?: number; mean_hits?: number; expected?: number; excess_pct?: number; z?: number
  p_better?: number | null; p_sequential?: number | null
  in_place?: number; in_place_expected?: number; ordered_checked?: number
  money_checked?: number; won?: number; spent?: number; won_priced?: number; return?: number
}
interface Data {
  summary: Row[]
  games: Array<{ slug: string; title: string; summary: Row[]; usual_return: number | null }>
  curves: Array<{ source: string; title: string; n: number; excess: number[]; upper: number[]; lower: number[] }>
}

const COLORS: Record<string, string> = { analysis_best: 'var(--accent)', analysis_consensus: 'var(--ball-dark)', chaos: '#7a3fb0', godmode: 'var(--hit)' }

function verdict(s: Row): string {
  if (!s.checked) return 'ещё нет сверенных прогнозов'
  if (s.p_sequential != null && s.p_sequential < 0.05) return 'устойчиво лучше случайного выбора'
  if (s.p_better != null && s.p_better < 0.05) return 'лучше случайного, но с учётом постоянного подсматривания — ещё не доказано'
  return 'в пределах случайности'
}

/** Сводка журнала по всем играм: можно ли доверять прогнозам. */
export function JournalOverview() {
  const [data, setData] = useState<Data | null>(null)
  useEffect(() => { fetch('/api/journal', { cache: 'no-store' }).then((r) => r.json()).then(setData) }, [])
  if (!data) return <main className="page"><p className="muted">Загрузка…</p></main>
  const total = data.summary.reduce((s, r) => s + (r.checked ?? 0), 0)
  return (
    <main className="page" data-testid="journal-overview">
      <h1>Итоги прогнозов</h1>
      <p className="note">
        Все прогнозы, записанные в журнал до тиража и сверенные после него, по всем играм ({nf.format(total)} шт.). Это
        единственная проверка, где метод не видел тиража заранее. «Последовательная p» учитывает, что результат
        смотрят после каждого тиража: обычное p при таком подсматривании рано или поздно опускается ниже 0,05 и у
        случайного выбора, а последовательное — нет. Пока она выше 0,05, преимущества нет.
      </p>

      <div className="table-wrap">
        <table className="data" data-testid="overview-summary">
          <thead>
            <tr>
              <th>Источник</th><th className="r">Сверено</th><th className="r">Угадано</th><th className="r">Ожидалось</th>
              <th className="r">Разница</th><th className="r">p</th><th className="r">Последовательная p</th>
              <th className="r">На своём месте</th><th className="r">Потрачено, ₽</th><th className="r">Выиграно, ₽</th>
              <th className="r">Возврат с рубля</th><th>Вывод</th>
            </tr>
          </thead>
          <tbody>
            {data.summary.map((s) => (
              <tr key={s.source} className={s.p_sequential != null && s.p_sequential < 0.05 ? 'sig' : ''}>
                <td>{s.title}</td>
                <td className="r num">{nf.format(s.checked)}</td>
                <td className="r num">{s.hits != null ? nf.format(s.hits) : '—'}</td>
                <td className="r num">{s.expected_total != null ? num(s.expected_total, 1) : '—'}</td>
                <td className="r num">{pct(s.excess_pct)}</td>
                <td className="r num">{s.p_better == null ? '—' : pval(s.p_better)}</td>
                <td className="r num">{s.p_sequential == null ? '—' : pval(s.p_sequential)}</td>
                <td className="r num">{s.in_place != null ? <>{s.in_place}<span className="sub">ожидалось {num(s.in_place_expected, 1)}</span></> : '—'}</td>
                <td className="r num">{s.spent != null ? nf.format(Math.round(s.spent)) : '—'}</td>
                <td className="r num">{s.won_priced != null ? nf.format(Math.round(s.won_priced)) : s.won != null ? nf.format(Math.round(s.won)) : '—'}</td>
                <td className="r num">{s.return != null ? num(s.return, 2) : '—'}</td>
                <td className="small">{verdict(s)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Потрачено — цена одного билета с прогнозом в каждом сверенном тираже, выиграно — реальные выплаты этих тиражей.
        Крупные выигрыши редки, поэтому возврат в рублях шумнее, чем угаданные числа.
      </p>

      {data.curves.length > 0 && (
        <>
          <h3>Накопленное превышение над случайным выбором</h3>
          <p className="muted small">
            Сумма (угадано − ожидалось) по всем сверенным прогнозам по порядку. Серые пунктиры — ±2σ: пока линия
            между ними, результат объясняется удачей. Настоящее преимущество выглядит как линия, которая уходит вверх
            и не возвращается.
          </p>
          <div className="curve-grid">
          {data.curves.map((c) => (
            <div key={c.source} data-testid={`curve-${c.source}`}>
              <h4>{c.title} — {nf.format(c.n)} {plural(c.n, 'прогноз', 'прогноза', 'прогнозов')}</h4>
              <LineChart series={[
                { name: c.title, values: c.excess, color: COLORS[c.source] ?? 'var(--accent)' },
                { name: '+2σ', values: c.upper, color: 'var(--muted)', dashed: true },
                { name: '−2σ', values: c.lower, color: 'var(--muted)', dashed: true },
              ]} height={260} />
            </div>
          ))}
          </div>
        </>
      )}

      <h3>По играм</h3>
      <div className="table-wrap">
        <table className="data compact" data-testid="overview-games">
          <thead>
            <tr><th>Игра</th><th>Источник</th><th className="r">Сверено</th><th className="r">Разница</th><th className="r">p</th>
              <th className="r">Возврат с рубля</th><th className="r">Обычный возврат игры</th></tr>
          </thead>
          <tbody>
            {data.games.flatMap((g) => g.summary.filter((s) => s.checked > 0).map((s, i) => (
              <tr key={g.slug + s.source}>
                <td>{i === 0 ? <Link href={`/games/${g.slug}`}>{g.title}</Link> : ''}</td>
                <td>{s.title}</td>
                <td className="r num">{s.checked}</td>
                <td className="r num">{pct(s.excess_pct)}</td>
                <td className="r num">{s.p_better == null ? <span className="muted">мало данных</span> : pval(s.p_better)}</td>
                <td className="r num">{s.return != null ? num(s.return, 2) : '—'}</td>
                <td className="r num">{i === 0 && g.usual_return != null ? num(g.usual_return, 2) : ''}</td>
              </tr>
            )))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        По отдельной игре прогнозов мало, и среди двух десятков игр одна-две почти всегда покажут p &lt; 0,05 просто
        случайно — смотрите на общий итог вверху.
      </p>
    </main>
  )
}
