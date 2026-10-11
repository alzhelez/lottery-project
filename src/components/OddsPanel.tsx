'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { nf } from './format'

export interface Pattern {
  key: string; hits: number[]; total: number; p: number; one_in: number | null; prize: number | null
  prize_source?: 'user' | 'archive' | null; archive_prize?: number | null
}
export interface Odds {
  supported: boolean
  reason?: string
  title: string
  format: string
  blocks?: Array<{ name: string; count: number; lo: number; hi: number }>
  patterns?: Pattern[]
  jackpot?: { key: string; p: number; one_in: number }
  combinations?: number
  price?: number | null
  expected_value?: number | null
  return_per_ruble?: number | null
  p_any_prize?: number | null
  price_source?: 'user' | 'archive' | null
  archive_draws?: number
  legal_prize_fund: number
}

export function oneIn(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  if (v < 10) return `1 из ${v.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}`
  return `1 из ${nf.format(Math.round(v))}`
}

function percent(p: number): string {
  if (p >= 0.001) return `${(p * 100).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}%`
  return `${(p * 100).toExponential(1).replace('.', ',')}%`
}

export function OddsPanel({ slug }: { slug: string }) {
  const [odds, setOdds] = useState<Odds | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [price, setPrice] = useState('')
  const [prizes, setPrizes] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  const apply = useCallback((o: Odds | null) => {
    setOdds(o)
    if (o?.supported) {
      // в поля попадает только введённое вами; выплаты из архива — подсказкой и в расчёте
      setPrice(o.price && o.price_source === 'user' ? String(o.price) : '')
      setPrizes(Object.fromEntries((o.patterns ?? []).filter((p) => p.prize_source === 'user').map((p) => [p.key, String(p.prize)])))
    }
  }, [])

  useEffect(() => {
    fetch(`/api/games/${slug}/odds`, { cache: 'no-store' }).then(async (r) => {
      const d = await r.json()
      if (!r.ok) setError(d.error)
      else apply(d.odds)
    })
  }, [slug, apply])

  // ожидаемый выигрыш считаем сразу по введённым числам, до сохранения
  const live = useMemo(() => {
    if (!odds?.patterns) return null
    let ev = 0
    let any = 0
    let entered = 0
    for (const p of odds.patterns) {
      const v = Number(prizes[p.key]?.replace(',', '.')) || p.archive_prize || 0
      if (v > 0) { ev += p.p * v; any += p.p; entered++ }
    }
    const pr = Number(price.replace(',', '.')) || (odds.price_source === 'archive' ? odds.price ?? 0 : 0)
    return { ev, any, entered, ret: pr > 0 && entered ? ev / pr : null }
  }, [odds, prizes, price])

  async function save() {
    setSaving(true)
    const body = {
      price: Number(price.replace(',', '.')) || null,
      prizes: Object.fromEntries(Object.entries(prizes).map(([k, v]) => [k, Number(v.replace(',', '.'))]).filter(([, v]) => (v as number) > 0)),
    }
    const r = await fetch(`/api/games/${slug}/odds`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    const d = await r.json()
    setSaving(false)
    if (r.ok) apply(d.odds)
    else setError(d.error)
  }

  if (error) return <p className="error">{error}</p>
  if (!odds) return <p className="muted">Считаю вероятности…</p>
  if (!odds.supported) return <p className="empty" data-testid="odds">{odds.reason}</p>

  const shown = odds.patterns!.filter((p) => p.total > 0)
  return (
    <section className="panel" data-testid="odds">
      <p>
        Вероятность каждого исхода билета посчитана точно: совпадения в каждом поле подчиняются гипергеометрическому
        распределению, поля независимы. Выбор чисел — любым методом — эти вероятности не меняет.
      </p>
      <dl className="facts">
        <div><dt>Главный приз ({odds.jackpot!.key})</dt><dd data-testid="jackpot-odds">{oneIn(odds.jackpot!.one_in)}</dd></div>
        <div><dt>Разных билетов</dt><dd>{nf.format(odds.combinations!)}</dd></div>
        <div>
          <dt>Возврат с рубля ставки</dt>
          <dd data-testid="return">{live?.ret != null ? live.ret.toLocaleString('ru-RU', { maximumFractionDigits: 3 }) : '—'}</dd>
          <dd className="sub">{live?.ret != null ? `по ${live.entered} введённым призам` : 'введите цену и призы'}</dd>
        </div>
      </dl>
      <div className="callout">
        По закону «О лотереях» (ст. 10) призовой фонд — не меньше {Math.round(odds.legal_prize_fund * 100)}% выручки.
        Значит, в среднем лотерея возвращает игрокам порядка половины ставок: с каждого рубля ожидаемый
        возврат около {odds.legal_prize_fund.toLocaleString('ru-RU')} ₽, если суперприз и накопления в итоге разыгрываются.
      </div>

      <h3>Цена билета и призы</h3>
      <p className="muted small">
        Возьмите их из правил игры на stoloto.ru (они меняются, автоматически их не проверить). Для делимых
        категорий и суперприза введите текущую или среднюю сумму. Пустые поля — исход без выигрыша.
      
        {(odds.archive_draws ?? 0) > 0 && (
          <> Серые значения в полях — медиана реальных выплат за последние {odds.archive_draws} тиражей из архива,
          они уже учтены в расчёте.</>
        )}
      </p>
      <div className="run-bar">
        <label className="budget">Цена билета, ₽
          <input type="text" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} data-testid="ticket-price"
            placeholder={odds.price_source === 'archive' && odds.price ? String(odds.price) : ''} />
        </label>
        <button className="btn" onClick={save} disabled={saving} data-testid="save-prizes">{saving ? 'Сохраняю…' : 'Сохранить'}</button>
      </div>

      <div className="table-wrap">
        <table className="data" data-testid="odds-table">
          <thead>
            <tr><th>Совпадения</th><th className="r">Вероятность</th><th className="r">Шанс</th><th className="r">Приз, ₽</th><th className="r">Вклад в ожидание, ₽</th></tr>
          </thead>
          <tbody>
            {shown.map((p) => {
              const v = Number(prizes[p.key]?.replace(',', '.')) || p.archive_prize || 0
              return (
                <tr key={p.key}>
                  <td className="num">{p.key}</td>
                  <td className="r num">{percent(p.p)}</td>
                  <td className="r num">{oneIn(p.one_in)}</td>
                  <td className="r">
                    <input className="prize-input" type="text" inputMode="decimal" aria-label={`Приз за ${p.key}`}
                      value={prizes[p.key] ?? ''} onChange={(e) => setPrizes({ ...prizes, [p.key]: e.target.value })}
                      placeholder={p.archive_prize ? String(Math.round(p.archive_prize)) : ''}
                      title={p.archive_prize ? 'Медиана реальных выплат из архива — введите своё значение, чтобы заменить' : undefined}
                      data-testid={`prize-${p.key}`} />
                  </td>
                  <td className="r num">{v > 0 ? (p.p * v).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) : ''}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {live && live.entered > 0 && (
        <p data-testid="ev-summary">
          Ожидаемый выигрыш с билета: <b>{live.ev.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽</b>,
          шанс выиграть хоть что-то — <b>{oneIn(1 / live.any)}</b>.
        </p>
      )}
    </section>
  )
}
