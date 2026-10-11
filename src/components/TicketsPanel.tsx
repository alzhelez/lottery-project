'use client'
import { useState } from 'react'
import { BlockBalls } from './Balls'
import { nf } from './format'

interface Ticket { blocks: number[][]; notes: string[] }
interface Generated {
  supported: boolean
  popularity?: { significant: boolean; verdict: string } | null
  reason?: string
  tickets?: Ticket[]
  blocks?: Array<{ name: string; count: number; lo: number; hi: number }>
  accepted_share?: number | null
  combinations?: number
}
interface Checked {
  supported: boolean
  valid?: boolean
  reason?: string
  blocks?: Array<{ block: string; flags: Array<{ text: string }> }>
  verdict?: string
}

function csv(tickets: Ticket[], names: string[]): string {
  const rows = [['№', ...names].join(';'), ...tickets.map((t, i) => [i + 1, ...t.blocks.map((b) => b.join(', '))].join(';'))]
  return '﻿' + rows.join('\r\n')
}

export function TicketsPanel({ slug }: { slug: string }) {
  const [count, setCount] = useState(5)
  const [gen, setGen] = useState<Generated | null>(null)
  const [mine, setMine] = useState('')
  const [checked, setChecked] = useState<Checked | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function call(body: Record<string, unknown>) {
    setBusy(true)
    setError(null)
    const r = await fetch(`/api/games/${slug}/tickets`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    const d = await r.json()
    setBusy(false)
    if (!r.ok) { setError(d.error); return null }
    return d
  }

  function download() {
    if (!gen?.tickets) return
    const blob = new Blob([csv(gen.tickets, (gen.blocks ?? []).map((b) => b.name))], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${slug}_tickets.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <section className="panel" data-testid="tickets">
      <p>
        Шанс выиграть у любой комбинации одинаковый. Но суперприз и делимые категории делятся между всеми
        победителями, а люди выбирают числа неслучайно: даты (до 31), месяцы (до 12), ряды подряд, прогрессии,
        числа из прошлого тиража. Генератор берёт случайные комбинации и оставляет те, в которых этих признаков
        нет, — при выигрыше делиться, скорее всего, придётся с меньшим числом людей. В играх с фиксированными
        призами это ничего не даёт.
      </p>
      <div className="run-bar">
        <label className="budget">Билетов
          <input type="number" min={1} max={50} value={count} onChange={(e) => setCount(Math.min(50, Math.max(1, Number(e.target.value) || 1)))} data-testid="ticket-count" />
        </label>
        <button className="btn" disabled={busy} onClick={async () => { const d = await call({ count }); if (d) setGen(d.tickets) }} data-testid="generate">
          Сгенерировать
        </button>
        {gen?.tickets && gen.tickets.length > 0 && <button className="btn btn-ghost" onClick={download}>Скачать CSV</button>}
      </div>
      {error && <p className="error">{error}</p>}
      {gen && !gen.supported && <p className="empty">{gen.reason}</p>}
      {gen?.supported && (
        <>
          {gen.popularity?.verdict && <div className="callout" data-testid="ticket-popularity">{gen.popularity.verdict}</div>}
          <ol className="tickets" data-testid="ticket-list">
            {gen.tickets!.map((t, i) => (
              <li key={i}>
                <BlockBalls blocks={t.blocks} size="md" />
                <span className="sub">{t.notes.join('; ')}</span>
              </li>
            ))}
          </ol>
          {gen.accepted_share != null && (
            <p className="muted small">
              Фильтр проходит {Math.round(gen.accepted_share * 100)}% из {nf.format(gen.combinations!)} комбинаций. Билеты
              в наборе мало пересекаются между собой.
            </p>
          )}
        </>
      )}

      <h3>Проверить свою комбинацию</h3>
      <div className="run-bar">
        <input className="combo-input" type="text" placeholder="1, 7, 15, 22 | 3, 9, 11, 18" value={mine}
          onChange={(e) => setMine(e.target.value)} aria-label="Ваша комбинация" data-testid="check-input" />
        <button className="btn btn-ghost" disabled={busy || !mine.trim()} onClick={async () => { const d = await call({ check: mine }); if (d) setChecked(d.check) }} data-testid="check">
          Проверить
        </button>
      </div>
      <p className="muted small">Числа через запятую, поля разделяйте знаком «|».</p>
      {checked && (
        <div className="callout" data-testid="check-result">
          {!checked.supported || !checked.valid ? checked.reason : (
            <>
              {checked.blocks!.flatMap((b) => b.flags.map((f, i) => <div key={`${b.block}-${i}`}>• {b.block}: {f.text}</div>))}
              <div>{checked.verdict}</div>
            </>
          )}
        </div>
      )}
    </section>
  )
}
