'use client'
import { useState } from 'react'
import { BlockBalls } from './Balls'
import { num, pct, pval } from './format'

interface LMetric { n: number; mean_hits: number; baseline: number; deficit_pct: number; p_lower: number; p_adjusted?: number }
export interface LeastResult {
  status: string; message?: string
  baseline: { mean: number }
  methods: Array<{ key: string; title: string; control: boolean; selection: LMetric; holdout: LMetric }>
  best_key: string
  conclusion: string
  next_prediction: { model: string; numbers: number[][] }
  next_consensus: number[][]
}

/** Наименее вероятные числа: анти-методы и их честная проверка (выпадают ли их числа реже случайных). */
export function LeastPanel({ least, drawNo }: { least?: LeastResult; drawNo: number | null }) {
  const [open, setOpen] = useState(false)
  if (!least) return null
  if (least.status !== 'ok') return <p className="muted small">Наименее вероятные числа: {least.message}</p>
  const rows = [...least.methods].sort((a, b) => a.selection.mean_hits - b.selection.mean_hits)
  return (
    <div className="predict-card least" data-testid="least">
      <h3>Наименее вероятные числа на тираж №{drawNo}</h3>
      <p className="muted">Анти-метод, лучший на отборе: «{least.next_prediction.model}» — эти числа, по его логике, выпадут с наименьшей вероятностью.</p>
      <BlockBalls blocks={least.next_prediction.numbers} tone="cold" size="md" />
      <h4>Консенсус наименее вероятных</h4>
      <p className="muted small">Числа с самым низким средним местом в рейтингах всех методов.</p>
      <BlockBalls blocks={least.next_consensus} tone="cold" size="sm" />
      <div className="callout" data-testid="least-conclusion">{least.conclusion}</div>
      <button className="link-btn" onClick={() => setOpen((v) => !v)}>{open ? 'Скрыть проверку анти-методов' : 'Как анти-методы угадывали на истории'}</button>
      {open && (
        <>
          <p className="muted small">
            Цель обратная: чем меньше чисел анти-метода выпало, тем лучше. Случайные числа выпадают в среднем {num(least.baseline.mean)} раза
            за тираж; «реже» — на сколько процентов меньше; p — шанс случайно получить столько же или меньше.
          </p>
          <div className="table-wrap">
            <table className="data compact" data-testid="least-table">
              <thead><tr><th>Анти-метод</th><th className="r">Отбор: выпало</th><th className="r">Контроль: выпало</th><th className="r">реже случайного</th><th className="r">p с поправкой</th></tr></thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.key} className={m.key === least.best_key ? 'best' : m.control ? 'control' : ''}>
                    <td>{m.title}</td>
                    <td className="r num">{num(m.selection.mean_hits)}</td>
                    <td className="r num">{num(m.holdout.mean_hits)}</td>
                    <td className="r num">{pct(m.holdout.deficit_pct)}</td>
                    <td className="r num">{m.control ? '—' : pval(m.holdout.p_adjusted)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <p className="muted small">Числа записываются в журнал («Наименее вероятные») и сверяются с тиражом: засчитывается, если их выпало меньше, чем случайных.</p>
    </div>
  )
}
