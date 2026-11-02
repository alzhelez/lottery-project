'use client'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { nf, num, pval } from './format'

interface Row {
  source: string; title: string; goal?: 'fewer'; checked: number; half: number
  share: number | null; expected: number; expected_share: number | null; p_better: number | null
}
interface Game {
  slug: string; title: string; threshold: string | null; rows: Row[]
  best: Row | null; worst: Row | null; tie: boolean
}

const MIN_RELIABLE = 30

function share(v: number | null | undefined): string {
  return v == null ? '—' : `${num(v * 100, 1)}%`
}

function method(r: Row | null, g: Game) {
  if (!r) return <span className="muted">—</span>
  return (
    <>
      {r.title}
      <span className="sub">
        {nf.format(r.half)} из {nf.format(r.checked)} ({share(r.share)}){r.checked < MIN_RELIABLE ? ' · мало прогнозов' : ''}
      </span>
      {g.tie && <span className="sub">у всех методов одинаково</span>}
    </>
  )
}

/** Статистика: сколько раз каждый метод угадал не меньше половины чисел, лучший и худший метод игры. */
export function StatsView() {
  const [games, setGames] = useState<Game[] | null>(null)
  useEffect(() => { fetch('/api/stats', { cache: 'no-store' }).then((r) => r.json()).then((d) => setGames(d.games)) }, [])
  if (!games) return <main className="page"><p className="muted">Загрузка…</p></main>
  return (
    <main className="page" data-testid="stats">
      <h1>Статистика</h1>
      <p className="note">
        По журналу прогнозов — только тем, что записаны до тиража и сверены после него. Для каждой игры и метода —
        сколько раз прогноз угадал <b>половину своих чисел или больше</b> (в «6 из 45» — от 3 из 6, в «4 из 20» — от 4 из
        8, считая все поля). Рядом — сколько таких раз в среднем дал бы случайный выбор того же числа чисел: метод
        полезен, только если заметно его обгоняет. Лучший и худший — по доле таких прогнозов.
      </p>

      {games.length === 0 ? (
        <p className="empty">Сверенных прогнозов пока нет — они появятся после анализа и следующего тиража.</p>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data" data-testid="stats-summary">
              <thead>
                <tr><th>Игра</th><th>Порог</th><th>Лучший метод</th><th>Худший метод</th></tr>
              </thead>
              <tbody>
                {games.map((g) => (
                  <tr key={g.slug} data-testid="stats-game">
                    <td><Link href={`/games/${g.slug}`}>{g.title}</Link></td>
                    <td className="num">{g.threshold ?? '—'}</td>
                    <td data-testid="stats-best">{method(g.best, g)}</td>
                    <td data-testid="stats-worst">{method(g.worst, g)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3>По методам</h3>
          <div className="table-wrap">
            <table className="data compact" data-testid="stats-methods">
              <thead>
                <tr>
                  <th>Игра</th><th>Метод</th><th className="r">Сверено</th><th className="r">Угадал ≥ половины</th>
                  <th className="r">Доля</th><th className="r">Случайный выбор</th><th className="r">p</th>
                </tr>
              </thead>
              <tbody>
                {games.flatMap((g) => g.rows.map((r, i) => {
                  const mark = g.tie ? '' : r.source === g.best?.source ? 'лучший'
                    : r.source === g.worst?.source ? 'худший' : ''
                  return (
                    <tr key={g.slug + r.source} data-testid="stats-row" className={r.goal ? 'muted' : ''}>
                      <td style={{ whiteSpace: 'nowrap' }}>{i === 0 ? <Link href={`/games/${g.slug}`}>{g.title}</Link> : ''}</td>
                      <td>
                        {r.title}
                        {mark && <span className={`status-tag ${mark === 'лучший' ? 'st-done' : 'st-error'}`} style={{ marginLeft: 8 }}>{mark}</span>}
                        {r.goal && <span className="sub">цель — выпасть реже, в лучшие и худшие не входит</span>}
                      </td>
                      <td className="r num">{nf.format(r.checked)}</td>
                      <td className="r num">{nf.format(r.half)}</td>
                      <td className="r num">{share(r.share)}</td>
                      <td className="r num">{num(r.expected, r.expected < 10 ? 2 : 1)}<span className="sub">{share(r.expected_share)}</span></td>
                      <td className="r num" style={{ whiteSpace: 'nowrap' }}>{r.p_better == null ? <span className="muted">мало данных</span> : pval(r.p_better)}</td>
                    </tr>
                  )
                }))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            p — шанс, что случайный выбор угадал бы половину чисел так же часто или чаще; считается от{' '}
            {MIN_RELIABLE} сверенных прогнозов. Среди многих игр и методов p &lt; 0,05 у одного-двух бывает просто случайно.
          </p>
        </>
      )}
    </main>
  )
}
