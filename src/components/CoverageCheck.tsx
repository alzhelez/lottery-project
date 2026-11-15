'use client'
import { useCallback, useEffect, useState } from 'react'
import { nf, plural } from './format'
import { useJob } from './useJob'

interface Coverage {
  built: boolean; days: number; draws: number; first_no: number | null; last_no: number | null
  with_predictions: number; complete: boolean
  methods: Array<{ source: string; short: string; title: string; archived: boolean; have: number; missing: number; na: number; restored: number }>
  missing_total: number; restored_total: number
}

/** Автоанализ игры: у всех ли тиражей архива есть предсказания каждого метода. Если нет — кнопка
 * «Пересчитать предсказания» (пересчёт истории прогнозов и анализа за период только для этой игры). */
export function CoverageCheck({ slug }: { slug: string }) {
  const [c, setC] = useState<Coverage | null>(null)
  const load = useCallback(() => {
    fetch(`/api/games/${slug}/coverage`, { cache: 'no-store' }).then((r) => r.json()).then(setC).catch(() => {})
  }, [slug])
  const job = useJob('retro', slug, () => load())
  // архивные методы (Л, З, Х): разовый расчёт прогноза на ближайшие тиражи — в журнал и в блок «Архив» обзора
  const archive = useJob('archive', slug, () => { load(); window.dispatchEvent(new Event('lottery:forecast')) })
  useEffect(() => { load() }, [load])
  if (!c || c.draws === 0) return null
  const gaps = c.methods.filter((m) => m.missing > 0)
  const total = c.methods.reduce((a, m) => a + m.have, 0)
  const head = `В архиве ${nf.format(c.draws)} ${plural(c.draws, 'тираж', 'тиража', 'тиражей')} (№${c.first_no}–${c.last_no})`
  const without = c.draws - c.with_predictions
  const origin = (
    <span className="sub" data-testid="coverage-origin">
      Из {nf.format(total)} предсказаний {nf.format(total - c.restored_total)} записаны в журнал до тиража,{' '}
      {nf.format(c.restored_total)} посчитаны задним числом — только по тиражам до каждого. Последние тиражи — на вкладке
      «Журнал прогнозов» (посчитанные задним числом помечены), весь архив — там же в выгрузке «все тиражи».
    </span>
  )
  const fix = (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <button type="button" className="btn" data-testid="coverage-fix" disabled={job.running}
        onClick={() => job.start({ days: c.days })}>
        {job.running ? 'Пересчитываю…' : 'Пересчитать предсказания'}
      </button>
      <span className="muted small">
        {job.running ? (job.job?.log?.slice(-1)[0] ?? 'все методы на каждом тираже архива — только по тиражам до него')
          : 'Все методы пройдут каждый тираж архива заново — только по тиражам до него. Это несколько минут.'}
      </span>
      {job.error && <span className="error">{job.error}</span>}
    </div>
  )
  const archived = c.methods.filter((m) => m.archived)
  const archiveBar = (
    <div data-testid="coverage-archive" style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--line-soft)' }}>
      <b>Архив методов</b>
      <p className="muted small" style={{ margin: '.3rem 0' }}>
        {archived.map((m) => `${m.short} — ${m.title}`).join(', ')}. В циклах автозапуска не считаются, в «Финальном
        предсказании» и в Telegram не участвуют. Кнопка считает их один раз: прогноз на ближайшие тиражи появится в
        блоке «Архив» карточки тиража и в журнале, после тиража — в статистике.
      </p>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-ghost" data-testid="archive-run" disabled={archive.running || job.running}
          onClick={() => archive.start()}>
          {archive.running ? 'Считаю архивные методы…' : 'Запустить архивные методы'}
        </button>
        <span className="muted small" data-testid="archive-status">
          {archive.running ? (archive.job?.progress?.model ?? archive.job?.log?.slice(-1)[0] ?? 'сравнение методов и «Порядок из хаоса»')
            : archive.job?.status === 'done' ? 'посчитаны — прогноз в блоке «Архив» карточки тиража'
              : `в истории: ${archived.map((m) => `${m.short} — ${nf.format(m.have)}`).join(', ')}`}
        </span>
        {(archive.error || archive.job?.status === 'error') && <span className="error">{archive.error ?? archive.job?.error}</span>}
      </div>
    </div>
  )
  return (
    <section className="card" data-testid="coverage" style={{ marginTop: 12 }}>
      <b>Автоанализ: предсказания по всем тиражам</b>
      {!c.built ? (
        <>
          <p className="small" data-testid="coverage-unbuilt">
            <span className="status-tag st-error">не посчитаны</span>{' '}
            {head}, предсказания на весь архив ещё не посчитаны — сейчас они есть только у{' '}
            {nf.format(c.with_predictions)} {plural(c.with_predictions, 'тиража', 'тиражей', 'тиражей')} (журнал и анализ за период).
          </p>
          {fix}
        </>
      ) : c.complete ? (
        <p className="small" data-testid="coverage-ok">
          <span className="status-tag st-done">всё на месте</span>{' '}
          {head}, предсказания есть у {nf.format(c.with_predictions)} — пропусков нет.
          {without > 0 && (
            <span className="sub" data-testid="coverage-na">
              У самых ранних {nf.format(without)} {plural(without, 'тиража', 'тиражей', 'тиражей')} предсказаний нет и быть не
              может: методам нужна история до тиража (разгон), а в длинных архивах анализ берёт последние 60 000 тиражей.
              «Режим Бога» по первой части архива отбирает методы, поэтому честные предсказания у него — только на
              остальную часть: {c.methods.filter((m) => !m.archived).map((m) => `${m.short} — ${nf.format(m.have)}`).join(', ')}.
            </span>
          )}
          {origin}
        </p>
      ) : (
        <>
          <p className="small" data-testid="coverage-gaps">
            <span className="status-tag st-error">есть пропуски</span>{' '}
            {head}, предсказания есть у {nf.format(c.with_predictions)}. Не хватает предсказаний активных методов:{' '}
            {gaps.map((m) => `${m.short} (${m.title}) — ${nf.format(m.missing)}`).join(', ')}.
            <span className="sub">Пропуски закрывает ближайший цикл автозапуска — или кнопка ниже.</span>
            {origin}
          </p>
          {fix}
        </>
      )}
      {archiveBar}
    </section>
  )
}
