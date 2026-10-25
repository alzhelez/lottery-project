'use client'
import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { BlockBalls } from './Balls'
import { nf, num, plural } from './format'

interface Ticket {
  id: string; draw_no: number; numbers: number[][]; price: number | null; note?: string; added_at: string
  status: 'pending' | 'checked' | 'invalid'; actual?: number[][]; hits_by_block?: number[]; hits?: number
  won?: number | null; won_manual?: number; draw_date?: string
  popularity?: { popular: boolean; flags: string[] }
}
interface Summary {
  total: number; checked: number; pending: number; pending_spent: number; spent: number; won: number
  winners: number; unknown_prize: number; balance: number; return: number | null; best: number
}
interface GameRow { slug: string; title: string; summary: Summary; tickets: Ticket[] }
interface Form { next_no: number | null; price: number | null; blocks: Array<{ name: string; count: number; lo: number; hi: number; mode: string; flexible: boolean }> }
interface Data { games: GameRow[]; summary: Summary; form?: Form }

const rub = (v: number | null | undefined) => (v == null ? '—' : `${nf.format(Math.round(v))} ₽`)
const wonOf = (t: Ticket) => (t.won_manual != null ? t.won_manual : t.won ?? null)

function Facts({ s }: { s: Summary }) {
  return (
    <dl className="facts" data-testid="mytickets-summary">
      <div>
        <dt>Билетов</dt>
        <dd>{nf.format(s.total)}</dd>
        <dd className="sub">сверено {nf.format(s.checked)}, ждут тиража {nf.format(s.pending)}{s.pending ? ` (${rub(s.pending_spent)})` : ''}</dd>
      </div>
      <div><dt>Потрачено</dt><dd data-testid="mt-spent">{rub(s.spent)}</dd><dd className="sub">по сверенным билетам</dd></div>
      <div>
        <dt>Выиграно</dt><dd data-testid="mt-won">{rub(s.won)}</dd>
        <dd className="sub">выигрышных {nf.format(s.winners)}{s.best > 0 ? `, лучший ${rub(s.best)}` : ''}{s.unknown_prize ? `; выплата неизвестна у ${s.unknown_prize}` : ''}</dd>
      </div>
      <div>
        <dt>Итог</dt>
        <dd className={s.balance < 0 ? 'warn' : ''} data-testid="mt-balance">{s.balance > 0 ? '+' : ''}{rub(s.balance)}</dd>
        <dd className="sub">возврат с рубля {s.return == null ? '—' : num(s.return, 2)}</dd>
      </div>
    </dl>
  )
}

function Row({ t, slug, showGame, title, onChange }: { t: Ticket; slug: string; showGame: boolean; title: string; onChange: () => void }) {
  const [edit, setEdit] = useState(false)
  const [val, setVal] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const won = wonOf(t)
  async function send(method: 'PATCH' | 'DELETE', body?: unknown) {
    setErr(null)
    const r = await fetch(method === 'DELETE' ? `/api/my-tickets?game=${slug}&id=${t.id}` : '/api/my-tickets', {
      method, headers: { 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
    })
    if (!r.ok) { setErr((await r.json()).error); return }
    setEdit(false)
    onChange()
  }
  return (
    <tr data-testid="mt-row">
      {showGame && <td><Link href={`/games/${slug}`}>{title}</Link></td>}
      <td className="num">№{t.draw_no}{t.draw_date && <span className="sub">{t.draw_date}</span>}</td>
      <td><BlockBalls blocks={t.numbers} actual={t.actual} size="sm" />{t.note && <span className="sub">{t.note}</span>}</td>
      <td className="r num">{rub(t.price)}</td>
      <td>
        {t.status === 'pending' ? <span className="status-tag st-pending">ждёт тиража</span>
          : t.status === 'invalid' ? <span className="muted">не сверить</span>
            : <span className="num">{(t.hits_by_block ?? []).join(' + ')}</span>}
      </td>
      <td className="r num">
        {edit ? (
          <span className="run-bar" style={{ margin: 0 }}>
            <input className="prize-input" type="number" min={0} value={val} onChange={(e) => setVal(e.target.value)} aria-label="Выигрыш, ₽" data-testid="mt-won-input" />{' '}
            <button className="link-btn" onClick={() => send('PATCH', { game: slug, id: t.id, won: Number(val) })} disabled={val === '' || Number(val) < 0}>сохранить</button>{' '}
            <button className="link-btn" onClick={() => setEdit(false)}>отмена</button>
          </span>
        ) : (
          <>
            {t.status !== 'checked' ? '—' : won == null ? <span className="muted">неизвестна</span>
              : won > 0 ? <b className="hit-text">{rub(won)}</b> : rub(0)}
            {t.won_manual != null && <span className="sub">вписан вручную</span>}
            {t.status === 'checked' && (
              <span className="sub">
                <button className="link-btn" onClick={() => { setVal(String(won ?? '')); setEdit(true) }}>вписать</button>
                {t.won_manual != null && <> · <button className="link-btn" onClick={() => send('PATCH', { game: slug, id: t.id, won: null })}>по таблице</button></>}
              </span>
            )}
          </>
        )}
        {err && <span className="sub error">{err}</span>}
      </td>
      <td className="small">
        {t.popularity ? (t.popularity.popular
          ? <span className="warn" title={t.popularity.flags.join('\n')}>похожа на популярную</span>
          : <span className="muted">не похожа на популярную</span>) : '—'}
      </td>
      <td><button className="link-btn" onClick={() => send('DELETE')} aria-label="Удалить билет" data-testid="mt-delete">удалить</button></td>
    </tr>
  )
}

function Table({ g, showGame, onChange }: { g: GameRow; showGame: boolean; onChange: () => void }) {
  const [all, setAll] = useState(false)
  const rows = all ? g.tickets : g.tickets.slice(0, 50)
  return (
    <>
      <div className="table-wrap">
        <table className="data" data-testid={`mt-table-${g.slug}`}>
          <thead>
            <tr>
              {showGame && <th>Игра</th>}<th>Тираж</th><th>Числа</th><th className="r">Цена</th><th>Угадано</th>
              <th className="r">Выигрыш</th><th>Комбинация</th><th />
            </tr>
          </thead>
          <tbody>{rows.map((t) => <Row key={t.id} t={t} slug={g.slug} title={g.title} showGame={showGame} onChange={onChange} />)}</tbody>
        </table>
      </div>
      {g.tickets.length > rows.length && <button className="link-btn" onClick={() => setAll(true)}>Показать все {nf.format(g.tickets.length)}</button>}
    </>
  )
}

/** Купленные билеты: внесение, сверка с тиражами и денежный итог. Без slug — по всем играм. */
export function MyTickets({ slug }: { slug?: string }) {
  const [data, setData] = useState<Data | null>(null)
  const [games, setGames] = useState<Array<{ slug: string; title: string }>>([])
  const [game, setGame] = useState(slug ?? '')
  const [form, setForm] = useState<Form | null>(null)
  const [numbers, setNumbers] = useState('')
  const [draws, setDraws] = useState(1)
  const [drawNo, setDrawNo] = useState('')
  const [price, setPrice] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [added, setAdded] = useState<string | null>(null)

  const load = useCallback(async () => {
    const r = await fetch(`/api/my-tickets${slug ? `?game=${slug}` : ''}`, { cache: 'no-store' })
    const d = await r.json()
    if (!r.ok) { setError(d.error); return }
    setData(d)
    if (slug) setForm(d.form ?? null)
  }, [slug])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (slug) return
    fetch('/api/games', { cache: 'no-store' }).then((r) => r.json())
      .then((d) => setGames((d.games ?? []).filter((g: { draws: number }) => g.draws > 0)))
  }, [slug])
  useEffect(() => {
    if (slug || !game) { if (!slug) setForm(null); return }
    fetch(`/api/my-tickets?game=${game}`, { cache: 'no-store' }).then((r) => r.json()).then((d) => setForm(d.form ?? null))
  }, [slug, game])

  async function add() {
    setBusy(true)
    setError(null)
    setAdded(null)
    const body: Record<string, unknown> = { game, numbers, draws }
    if (drawNo.trim()) body.draw_no = Number(drawNo)
    if (price.trim()) body.price = Number(price.replace(',', '.'))
    if (note.trim()) body.note = note.trim()
    const r = await fetch('/api/my-tickets', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    const d = await r.json()
    setBusy(false)
    if (!r.ok) { setError(d.error); return }
    const list = d.added as Ticket[]
    setAdded(list.length === 1 ? `Билет на тираж №${list[0].draw_no} внесён.` : `Внесено ${list.length} ${plural(list.length, 'строка', 'строки', 'строк')}: тиражи №${list[0].draw_no}–${list[list.length - 1].draw_no}.`)
    setNumbers('')
    load()
  }

  const hint = form?.blocks.map((b) => `${b.name}: ${b.flexible ? `от 1 до ${b.count}` : b.count} из ${b.lo}–${b.hi}`).join('; ')
  const content = (
    <>
      <p className="note">
        Сюда вносятся билеты, которые вы действительно купили. Когда тираж загружен, билет сверяется: сколько чисел
        угадано и сколько он выиграл по таблице призов этого тиража. Итог — сколько потрачено и сколько выиграно
        на самом деле. Если выплата неизвестна (таблицы призов нет в архиве), выигрыш можно вписать вручную.
      </p>

      <div className="predict-card" data-testid="mt-form">
        <h3>Внести билет</h3>
        <div className="run-bar">
          {!slug && (
            <label className="budget">Игра
              <select value={game} onChange={(e) => setGame(e.target.value)} data-testid="mt-game">
                <option value="">— выберите —</option>
                {games.map((g) => <option key={g.slug} value={g.slug}>{g.title}</option>)}
              </select>
            </label>
          )}{' '}
          <input className="combo-input" type="text" placeholder="1, 7, 15, 22 | 3, 9, 11, 18" value={numbers}
            onChange={(e) => setNumbers(e.target.value)} aria-label="Числа билета" data-testid="mt-numbers" />
        </div>
        {hint && <p className="muted small">{hint}. Числа через запятую, поля разделяйте знаком «|».</p>}
        <div className="run-bar">
          <label className="budget">Тираж №
            <input className="prize-input" type="number" min={1} placeholder={form?.next_no ? String(form.next_no) : 'авто'}
              value={drawNo} onChange={(e) => setDrawNo(e.target.value)} data-testid="mt-draw" />
          </label>{' '}
          <label className="budget">на тиражей
            <input type="number" min={1} max={100} value={draws} onChange={(e) => setDraws(Math.min(100, Math.max(1, Number(e.target.value) || 1)))} data-testid="mt-draws" />
          </label>{' '}
          <label className="budget">Цена за тираж, ₽
            <input className="prize-input" type="number" min={0} placeholder={form?.price != null ? String(form.price) : 'авто'}
              value={price} onChange={(e) => setPrice(e.target.value)} data-testid="mt-price" />
          </label>{' '}
          <input className="combo-input" style={{ width: 'min(14rem, 100%)' }} type="text" maxLength={200} placeholder="заметка (необязательно)"
            value={note} onChange={(e) => setNote(e.target.value)} aria-label="Заметка" />
        </div>
        <button className="btn" disabled={busy || !game || !numbers.trim()} onClick={add} data-testid="mt-add">
          {busy ? 'Вношу…' : 'Внести'}
        </button>
        {error && <p className="error" data-testid="mt-error">{error}</p>}
        {added && <p className="muted" data-testid="mt-added">{added}</p>}
        <p className="muted small">
          Номер тиража по умолчанию — ближайший будущий. Комбинацию программа сразу проверяет на «популярность»: шанс
          выигрыша от этого не меняется, но популярный суперприз чаще приходится делить. Непопулярные комбинации — во
          вкладке «Билеты» на странице игры.
        </p>
      </div>

      {!data ? <p className="muted">Загрузка…</p> : data.summary.total === 0 ? (
        <p className="empty" data-testid="mt-empty">Билетов пока нет.</p>
      ) : (
        <>
          <Facts s={data.summary} />
          {data.games.filter((g) => g.tickets.length).map((g) => (
            <div key={g.slug}>
              {!slug && (
                <h3 className="section-title">
                  {g.title} — {nf.format(g.summary.total)} {plural(g.summary.total, 'билет', 'билета', 'билетов')}, итог{' '}
                  {g.summary.balance > 0 ? '+' : ''}{rub(g.summary.balance)}
                </h3>
              )}
              <Table g={g} showGame={false} onChange={load} />
            </div>
          ))}
        </>
      )}
    </>
  )
  return slug ? <section className="panel" data-testid="mytickets">{content}</section>
    : <main className="page" data-testid="mytickets"><h1>Мои билеты</h1>{content}</main>
}
