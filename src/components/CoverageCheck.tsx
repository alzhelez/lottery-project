'use client'
import { useCallback, useEffect, useState } from 'react'
import { nf } from './format'
import { useJob } from './useJob'

interface Coverage {
  days: number; draws: number; first_no: number | null; last_no: number | null; complete: boolean
  methods: Array<{ source: string; short: string; title: string; have: number; missing: number; restored: number }>
  missing_total: number; restored_total: number
}

/** Автоанализ игры: у всех ли тиражей периода есть предсказания каждого метода. Если нет — кнопка
 * «Пересчитать предсказания» (анализ за период только для этой игры). */
export function CoverageCheck({ slug }: { slug: string }) {
  const [c, setC] = useState<Coverage | null>(null)
  const load = useCallback(() => {
    fetch(`/api/games/${slug}/coverage`, { cache: 'no-store' }).then((r) => r.json()).then(setC).catch(() => {})
  }, [slug])
  const job = useJob('retro', slug, () => load())
  useEffect(() => { load() }, [load])
  if (!c || c.draws === 0) return null
  const gaps = c.methods.filter((m) => m.missing > 0)
  const total = c.methods.reduce((a, m) => a + m.have, 0)
  const origin = (
    <span className="sub" data-testid="coverage-origin">
      Из {nf.format(total)} предсказаний {nf.format(total - c.restored_total)} записаны в журнал до тиража,{' '}
      {nf.format(c.restored_total)} восстановлены анализом за период (только по тиражам до каждого). И те и другие — на
      вкладке «Журнал прогнозов»; восстановленные помечены.
    </span>
  )
  return (
    <section className="card" data-testid="coverage" style={{ marginTop: 12 }}>
      <b>Автоанализ: предсказания по тиражам</b>
      {c.complete ? (
        <p className="small" data-testid="coverage-ok">
          <span className="status-tag st-done">всё на месте</span>{' '}
          За {c.days} дн. сыграно {nf.format(c.draws)} тиражей (№{c.first_no}–{c.last_no}) — у каждого есть предсказания всех методов.
          {origin}
        </p>
      ) : (
        <>
          <p className="small" data-testid="coverage-gaps">
            <span className="status-tag st-error">есть пропуски</span>{' '}
            За {c.days} дн. сыграно {nf.format(c.draws)} тиражей (№{c.first_no}–{c.last_no}). Не хватает предсказаний:{' '}
            {gaps.map((m) => `${m.short} (${m.title}) — ${nf.format(m.missing)}`).join(', ')}.
            {origin}
          </p>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <button type="button" className="btn" data-testid="coverage-fix" disabled={job.running}
              onClick={() => job.start({ days: c.days })}>
              {job.running ? 'Пересчитываю…' : 'Пересчитать предсказания'}
            </button>
            <span className="muted small">
              {job.running ? (job.job?.log?.slice(-1)[0] ?? 'все методы на каждом тираже периода — только по тиражам до него')
                : 'Все методы пройдут каждый тираж периода заново — только по тиражам до него.'}
            </span>
            {job.error && <span className="error">{job.error}</span>}
          </div>
        </>
      )}
    </section>
  )
}
