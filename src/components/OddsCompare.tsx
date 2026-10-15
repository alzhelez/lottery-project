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
  const byArchive = (rows ?? []).filter((r) => !r.supported && r.archive)
    .sort((a, b) => Number(b.active) - Number(a.active) || b.archive!.return - a.archive!.return)
  const skipped = (rows ?? []).filter((r) => !r.supported && !r.archive)
  const ret = (v: number | null | undefined) => (v != null ? v.toLocaleString('ru-RU', { maximumFractionDigits: 3 }) : '—')
  return (
    <main className="page">
      <h1>Шансы игр</h1>
      <p className="lead">Точные вероятности главного приза, ожидаемый возврат с рубля ставки и он же по реальным выплатам из архива.</p>
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
              <tr><th>Игра</th><th>Формат</th><th className="r">Главный приз</th><th className="r">Разных билетов</th><th className="r">Цена, ₽</th><th className="r">Возврат с рубля</th><th className="r">По архиву</th></tr>
            </thead>
            <tbody>
              {ok.map((r) => (
                <tr key={r.slug} className={r.active ? '' : 'control'}>
                  <td><Link href={`/games/${r.slug}`}>{r.title}</Link>{!r.active && <span className="sub">устаревшая</span>}</td>
                  <td className="small">{r.format}</td>
                  <td className="r num">{oneIn(r.jackpot!.one_in)}</td>
                  <td className="r num">{nf.format(r.combinations!)}</td>
                  <td className="r num">{r.price ?? '—'}</td>
                  <td className="r num">{ret(r.return_per_ruble)}</td>
                  <td className="r num">{ret(r.archive?.return)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {byArchive.length > 0 && (
        <>
          <h2 style={{ marginTop: '2rem' }}>Без точной формулы — по архиву</h2>
          <p className="muted small">Бинго (туры) и ставки на цифры: шанс и возврат посчитаны по реальным итогам последних тиражей.</p>
          <div className="table-wrap">
            <table className="data" data-testid="odds-archive-compare">
              <thead><tr><th>Игра</th><th className="r">Тиражей</th><th className="r">Цена, ₽</th><th className="r">Шанс выиграть</th><th className="r">Возврат с рубля</th></tr></thead>
              <tbody>
                {byArchive.map((r) => (
                  <tr key={r.slug} className={r.active ? '' : 'control'}>
                    <td><Link href={`/games/${r.slug}`}>{r.title}</Link>{!r.active && <span className="sub">устаревшая</span>}</td>
                    <td className="r num">{r.archive!.draws}</td>
                    <td className="r num">{r.archive!.price}</td>
                    <td className="r num">{r.archive!.p_any > 0 ? oneIn(1 / r.archive!.p_any) : '—'}</td>
                    <td className="r num">{ret(r.archive!.return)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {skipped.length > 0 && (
        <p className="muted small">Без расчёта: {skipped.map((r) => `${r.title} — ${r.reason}`).join('; ')}</p>
      )}
    </main>
  )
}
