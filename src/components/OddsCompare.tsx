'use client'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { nf } from './format'
import { oneIn, type Odds } from './OddsPanel'

type Row = Odds & { slug: string; active: boolean }

export function OddsCompare() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    fetch('/api/odds', { cache: 'no-store' }).then(async (r) => {
      const d = await r.json()
      if (!r.ok) { setError(d.error); return }
      setRows(Object.entries(d.odds as Record<string, Odds & { active: boolean }>).map(([slug, o]) => ({ ...o, slug })))
    })
  }, [])
  const ok = (rows ?? []).filter((r) => r.supported).sort((a, b) => Number(b.active) - Number(a.active) || a.jackpot!.one_in - b.jackpot!.one_in)
  const skipped = (rows ?? []).filter((r) => !r.supported)
  return (
    <main className="page">
      <h1>Шансы игр</h1>
      <p className="lead">Точные вероятности главного приза и, если вы ввели призы, ожидаемый возврат с рубля ставки.</p>
      <p className="note">
        По закону «О лотереях» (ст. 10) призовой фонд — не меньше 50% выручки, так что в среднем любая из этих
        лотерей возвращает игрокам около половины ставок. Цену билета и призы вводят на вкладке «Шансы» страницы игры.
      </p>
      {error && <p className="error">{error}</p>}
      {!rows && !error && <p className="muted">Считаю…</p>}
      {ok.length > 0 && (
        <div className="table-wrap">
          <table className="data" data-testid="odds-compare">
            <thead>
              <tr><th>Игра</th><th>Формат</th><th className="r">Главный приз</th><th className="r">Разных билетов</th><th className="r">Цена, ₽</th><th className="r">Возврат с рубля</th></tr>
            </thead>
            <tbody>
              {ok.map((r) => (
                <tr key={r.slug} className={r.active ? '' : 'control'}>
                  <td><Link href={`/games/${r.slug}`}>{r.title}</Link>{!r.active && <span className="sub">устаревшая</span>}</td>
                  <td className="small">{r.format}</td>
                  <td className="r num">{oneIn(r.jackpot!.one_in)}</td>
                  <td className="r num">{nf.format(r.combinations!)}</td>
                  <td className="r num">{r.price ?? '—'}</td>
                  <td className="r num">{r.return_per_ruble != null ? r.return_per_ruble.toLocaleString('ru-RU', { maximumFractionDigits: 3 }) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {skipped.length > 0 && (
        <p className="muted small">Без расчёта: {skipped.map((r) => `${r.title} — ${r.reason}`).join('; ')}</p>
      )}
    </main>
  )
}
