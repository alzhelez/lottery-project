'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { nf } from './format'

export interface Pattern {
  key: string; hits: number[]; total: number; p: number; one_in: number | null; prize: number | null
  prize_source?: 'user' | 'archive' | 'rules' | null; archive_prize?: number | null
  official_prize?: number | null; fund_share?: number | null; superprize?: boolean
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
  price_source?: 'user' | 'archive' | 'rules' | null
  archive_draws?: number
  legal_prize_fund: number
  archive?: ArchiveStats | null
  variants?: KenoVariant[] | null
  rules?: { prize_fund_pct: number | null; min_prize: number | null; jackpot_guaranteed: number | null; super_prize: number | null } | null
  next_draw?: { number: number; date: string | null; return: number; return_without_super: number; super_prize: number; verdict: string; lototron?: boolean | null } | null
}

export interface ArchiveStats {
  draws: number; from: number; to: number; price: number; bets_per_draw: number; return: number; p_any: number
  categories: Array<{ label: string; chance: number; one_in: number | null; prize: number | null; return: number; winners: number }>
}

export interface KenoVariant {
  pick: number
  rows: Array<{ hits: number; p: number; one_in: number | null; prize: number | null }>
  expected_value: number | null; return_per_ruble: number | null; p_any_prize: number | null
}

const rub = (v: number) => v.toLocaleString('ru-RU', { maximumFractionDigits: v < 10 ? 2 : 0 })
const ret3 = (v: number | null | undefined) => (v != null ? v.toLocaleString('ru-RU', { maximumFractionDigits: 3 }) : '—')

/** Шансы и возврат по реальным итогам тиражей: победители / проданные ставки, выплаты. */
export function ArchiveOdds({ a }: { a: ArchiveStats }) {
  const shown = a.categories.filter((c) => c.winners > 0 || (c.prize ?? 0) > 0)
  return (
    <section data-testid="archive-odds">
      <h3>Шансы по архиву</h3>
      <p className="muted small">
        По итогам последних {a.draws} тиражей (№{a.from}–{a.to}): шанс категории — доля выигравших ставок
        (победители ÷ проданные ставки, в среднем {nf.format(Math.round(a.bets_per_draw))} за тираж), приз — медиана выплаты,
        возврат — сколько из каждого рубля ставок вернулось игрокам в этой категории. Это оценка по истории, а не формула:
        в ней уже учтены популярность комбинаций и увеличенные ставки.
      </p>
      <dl className="facts">
        <div><dt>Возврат с рубля по архиву</dt><dd data-testid="archive-return">{ret3(a.return)}</dd>
          <dd className="sub">цена ставки ≈ {rub(a.price)} ₽</dd></div>
        <div><dt>Шанс выиграть хоть что-то</dt><dd>{a.p_any > 0 ? oneIn(1 / a.p_any) : '—'}</dd></div>
      </dl>
      <div className="table-wrap">
        <table className="data" data-testid="archive-table">
          <thead><tr><th>Категория</th><th className="r">Шанс на ставку</th><th className="r">Приз, ₽</th><th className="r">Возврат с рубля</th></tr></thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.label}>
                <td>{c.label}</td>
                <td className="r num">{oneIn(c.one_in)}</td>
                <td className="r num">{c.prize != null ? rub(c.prize) : '—'}</td>
                <td className="r num">{ret3(c.return)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** Кено: билет на K чисел (1…10) при 20 выпавших из 80 — точные шансы и возврат для каждого K. */
export function KenoVariants({ variants, price }: { variants: KenoVariant[]; price: number | null | undefined }) {
  const [pick, setPick] = useState(variants[variants.length - 1].pick)
  const v = variants.find((x) => x.pick === pick) ?? variants[0]
  const best = variants.filter((x) => x.return_per_ruble != null).sort((a, b) => b.return_per_ruble! - a.return_per_ruble!)[0]
  return (
    <section data-testid="keno-variants">
      <h3>Сколько чисел выбрать</h3>
      <p className="muted small">
        В Кено выбирают от 1 до {variants.length} чисел, а выпадает 20 из 80. Вероятности посчитаны точно
        (гипергеометрическое распределение), призы — медиана выплат за последние 500 тиражей{price ? `, ставка ${rub(price)} ₽` : ''}.
        Исходы, по которым за это время не было ни одного победителя (например, 10 из 10), в возврат не вошли.
        {best && <> Больше всего в среднем возвращает билет на {best.pick} {best.pick === 1 ? 'число' : best.pick < 5 ? 'числа' : 'чисел'} — {ret3(best.return_per_ruble)} с рубля.</>}
      </p>
      <div className="table-wrap">
        <table className="data" data-testid="keno-table">
          <thead><tr><th>Чисел в билете</th><th className="r">Шанс выиграть</th><th className="r">Возврат с рубля</th></tr></thead>
          <tbody>
            {variants.map((x) => (
              <tr key={x.pick} className={x.pick === pick ? 'selected' : ''} onClick={() => setPick(x.pick)} style={{ cursor: 'pointer' }}>
                <td className="num">{x.pick}</td>
                <td className="r num">{x.p_any_prize ? oneIn(1 / x.p_any_prize) : '—'}</td>
                <td className="r num">{ret3(x.return_per_ruble)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h4>Билет на {v.pick}: исходы</h4>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Угадано</th><th className="r">Шанс</th><th className="r">Приз, ₽</th></tr></thead>
          <tbody>
            {v.rows.map((r) => (
              <tr key={r.hits}><td className="num">{r.hits} из {v.pick}</td><td className="r num">{oneIn(r.one_in)}</td>
                <td className="r num">{r.prize != null ? rub(r.prize) : '—'}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
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
      const v = Number(prizes[p.key]?.replace(',', '.')) || p.official_prize || p.archive_prize || 0
      if (v > 0) { ev += p.p * v; any += p.p; entered++ }
    }
    const pr = Number(price.replace(',', '.')) || (odds.price_source === 'archive' || odds.price_source === 'rules' ? odds.price ?? 0 : 0)
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
  if (!odds.supported) {
    return (
      <section className="panel" data-testid="odds">
        <p className="empty">{odds.reason}</p>
        {odds.archive ? <ArchiveOdds a={odds.archive} /> : <p className="muted small">Данных о выплатах в архиве пока мало — загрузите тиражи.</p>}
      </section>
    )
  }

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
      {odds.next_draw && (
        <div className={`callout ${odds.next_draw.return >= 1 ? 'lv-signal' : ''}`} data-testid="next-draw-return">
          <strong>Ближайший тираж №{odds.next_draw.number}</strong>
          {odds.next_draw.date && ` (${odds.next_draw.date.replace('T', ' ').slice(0, 16)})`}: суперприз{' '}
          {nf.format(Math.round(odds.next_draw.super_prize))} ₽, ожидаемый возврат{' '}
          <b>{odds.next_draw.return.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</b> на рубль
          (без суперприза — {odds.next_draw.return_without_super.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}).
          <span className="sub">{odds.next_draw.verdict}</span>
        </div>
      )}
      <div className="callout">
        По закону «О лотереях» (ст. 10) призовой фонд — не меньше {Math.round(odds.legal_prize_fund * 100)}% выручки.
        {odds.rules?.prize_fund_pct ? ` В этой игре по правилам — ${odds.rules.prize_fund_pct}%.` : ''}
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
        {odds.patterns!.some((p) => p.official_prize) && <> Фиксированные выигрыши подставлены из официальной таблицы stoloto.ru (вкладка «Правила»).</>}
      </p>
      <div className="run-bar">
        <label className="budget">Цена билета, ₽
          <input type="text" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} data-testid="ticket-price"
            placeholder={(odds.price_source === 'archive' || odds.price_source === 'rules') && odds.price ? String(odds.price) : ''} />
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
              const v = Number(prizes[p.key]?.replace(',', '.')) || p.official_prize || p.archive_prize || 0
              return (
                <tr key={p.key}>
                  <td className="num">{p.key}</td>
                  <td className="r num">{percent(p.p)}</td>
                  <td className="r num">{oneIn(p.one_in)}</td>
                  <td className="r">
                    <input className="prize-input" type="text" inputMode="decimal" aria-label={`Приз за ${p.key}`}
                      value={prizes[p.key] ?? ''} onChange={(e) => setPrizes({ ...prizes, [p.key]: e.target.value })}
                      placeholder={p.superprize ? 'суперприз' : p.official_prize ? String(Math.round(p.official_prize)) : p.archive_prize ? String(Math.round(p.archive_prize)) : ''}
                      title={p.official_prize ? 'Фиксированный выигрыш по официальной таблице stoloto.ru' : p.archive_prize ? `Медиана реальных выплат из архива${p.fund_share ? ` (по правилам — ${p.fund_share}% призового фонда)` : ''} — введите своё значение, чтобы заменить` : undefined}
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
      {odds.variants && odds.variants.length > 0 && <KenoVariants variants={odds.variants} price={odds.price} />}
      {odds.archive && <ArchiveOdds a={odds.archive} />}
    </section>
  )
}
