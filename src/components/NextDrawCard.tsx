'use client'
import { useCallback, useEffect, useState } from 'react'
import { BlockBalls } from './Balls'
import { nf, num, pval } from './format'
import { useJob } from './useJob'

interface Rec { checked: number; mean_hits?: number; expected?: number; p_sequential?: number | null; goal?: string }
interface Source { source: string; title: string; detail: string; numbers: number[][]; made_at: string | null; record: Rec | null }
interface NextData {
  draw_no: number | null; date?: string | null; how?: string | null; last_no?: number; active: boolean
  analysis_at?: string | null; super_prize?: number | null
  sources: Source[]
  least: { numbers: number[][] | null; model: string; consensus: number[][] | null; conclusion: string | null; record: Rec | null } | null
}

const SHORT: Record<string, string> = { analysis_best: 'Л', analysis_consensus: 'К', chaos: 'Х', godmode: 'Б' }

function left(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const two = (v: number) => String(v).padStart(2, '0')
  return d ? `${d} д ${two(h)}:${two(m)}:${two(sec)}` : `${two(h)}:${two(m)}:${two(sec)}`
}

function RecordLine({ r, fewer }: { r: Rec | null; fewer?: boolean }) {
  if (!r || !r.checked) return <span className="sub">по журналу: ещё нет сверенных прогнозов</span>
  const proven = r.p_sequential != null && r.p_sequential < 0.05
  return (
    <span className="sub">
      по журналу: {nf.format(r.checked)} сверено, {fewer ? 'выпало' : 'угадано'} в среднем {num(r.mean_hits, 2)} при {num(r.expected, 2)} у случайного выбора
      {r.p_sequential != null && <>, последовательное p {pval(r.p_sequential)}</>}
      {' — '}{proven ? <b className="hit-text">{fewer ? 'устойчиво реже случайного' : 'устойчиво лучше случайного'}</b> : fewer ? 'пока не реже случайных чисел' : 'пока не лучше случайного выбора'}
    </span>
  )
}

/** Ближайший тираж: таймер, прогнозы всех источников (те же, что в журнале), наименее вероятные числа. */
export function NextDrawCard({ slug, stamp, onAnalyzed }: { slug: string; stamp?: string | null; onAnalyzed: () => void }) {
  const [data, setData] = useState<NextData | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const load = useCallback(async () => {
    try {
      const r = await fetch(`/api/games/${slug}/next`, { cache: 'no-store' })
      if (r.ok) setData(await r.json())
    } catch { /* сервер перезапускается */ }
  }, [slug])
  const analyze = useJob('analyze', slug, () => { load(); onAnalyzed() })
  const fetchJob = useJob('fetch', slug, () => { analyze.start() })
  // перечитать после любого пересчёта анализа (stamp — время отчёта)
  useEffect(() => { load() }, [load, stamp])
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  if (!data) return null
  const busy = fetchJob.running || analyze.running
  const refresh = (
    <button className="btn btn-ghost" disabled={busy} onClick={() => fetchJob.start()} data-testid="next-refresh">
      {fetchJob.running ? 'Загружаю тиражи…' : analyze.running ? 'Считаю прогноз…' : 'Загрузить тиражи и обновить прогноз'}
    </button>
  )
  if (data.draw_no == null) {
    return (
      <section className="next-card" data-testid="next-card">
        <p className="muted">{data.active ? 'Прогноза на ближайший тираж ещё нет — запустите анализ.' : 'Игра устарела: тиражей давно не было, прогнозы не пишутся.'}</p>
      </section>
    )
  }
  const at = data.date ? new Date(data.date).getTime() : null
  const passed = at != null && at <= now
  return (
    <section className="next-card" data-testid="next-card">
      <div className="next-head">
        <div>
          <h2>Ближайший тираж №{data.draw_no}</h2>
          <p className="muted small">
            {data.date ? `${data.date.replace('T', ' ').slice(0, 16)}` : 'время тиража неизвестно'}
            {data.how ? ` — ${data.how}` : ''}
            {data.super_prize ? `; суперприз ${nf.format(data.super_prize)} ₽` : ''}
          </p>
        </div>
        {at != null && !passed && (
          <div className="countdown" data-testid="countdown" aria-live="off">
            <span className="countdown-label">до тиража</span>
            <span className="countdown-value">{left(at - now)}</span>
          </div>
        )}
      </div>

      {passed ? (
        <div className="banner" data-testid="next-stale">
          Тираж №{data.draw_no} уже прошёл или идёт. Чтобы получить прогноз на следующий, загрузите новые тиражи —
          анализ запустится сам.
          <div className="run-bar">{refresh}</div>
        </div>
      ) : (
        <>
          <div className="next-sources">
            {data.sources.map((s) => (
              <div key={s.source} className="next-source" data-testid={`next-${s.source}`}>
                <span className="src-chip" title={s.title}>{SHORT[s.source]}</span>
                <div>
                  <div className="src-title">{s.title}{s.detail && <span className="muted">: {s.detail}</span>}</div>
                  <BlockBalls blocks={s.numbers} size={s.source === 'analysis_best' ? 'lg' : 'md'} />
                  <RecordLine r={s.record} />
                </div>
              </div>
            ))}
          </div>
          {data.least?.numbers && (
            <div className="next-least" data-testid="next-least">
              <h3>Наименее вероятно выпадут</h3>
              <p className="muted small">Анти-метод «{data.least.model}» — числа, которые по его логике выпадут с наименьшей вероятностью.</p>
              <BlockBalls blocks={data.least.numbers} tone="cold" size="md" />
              {data.least.consensus && (
                <>
                  <p className="muted small">Консенсус наименее вероятных по всем методам:</p>
                  <BlockBalls blocks={data.least.consensus} tone="cold" size="sm" />
                </>
              )}
              <RecordLine r={data.least.record} fewer />
            </div>
          )}
          <p className="muted small">
            Эти числа записаны в журнал и будут сверены с тиражом.{' '}
            {data.sources.some((s) => s.record?.p_sequential != null && s.record.p_sequential < 0.05)
              ? 'Источник с пометкой «устойчиво лучше случайного» по журналу этой игры действительно угадывает чаще случайного выбора.'
              : 'Пока ни один источник не стал «устойчиво лучше случайного», любые числа так же хороши, как эти.'}
          </p>
          <div className="run-bar">{refresh}</div>
        </>
      )}
      {(fetchJob.job?.status === 'error' || analyze.job?.status === 'error') && (
        <p className="error">Ошибка: {fetchJob.job?.error ?? analyze.job?.error}</p>
      )}
    </section>
  )
}
