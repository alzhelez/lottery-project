'use client'
import { useCallback, useEffect, useState } from 'react'
import { BlockBalls } from './Balls'
import { LineChart } from './Charts'
import { duration, num, pct, pval } from './format'
import type { Info } from './GameView'
import { useJob } from './useJob'

interface Metric { mean_hits: number; excess_pct: number; p_better: number; n: number }
interface GodResult {
  generated_at: string
  last_draw_no: number
  complete: boolean
  stage: string
  elapsed_seconds: number
  budget_seconds: number
  experts: number
  evaluation: { from: number; split: number; to: number }
  baseline: { mean: number }
  strategies: Array<{ key: string; title: string; first: Metric; second: Metric }>
  chosen: string
  chosen_title: string
  best_expert: { title: string; first: Metric; second: Metric }
  top_experts: Array<{ key: string; title: string; first: Metric; second: Metric }>
  random_control_excess: number[]
  curves: { chosen: number[]; best_expert: number[]; random: number[] }
  switches: number
  timeline: Array<{ no: number; date: string; predicted: number[][]; actual: number[][]; hits: number; model: string | null }>
  next: { no: number; numbers: number[][]; model: string | null; strategy: string }
  verdict: string
  exhausted?: boolean
  resumed?: boolean
}

interface GodState { resumable: boolean; exhausted: boolean; elapsed: number; experts: number }

const MAX_S = 8 * 3600

export function GodModePanel({ info }: { info: Info }) {
  const [res, setRes] = useState<GodResult | null>(null)
  const [state, setState] = useState<GodState | null>(null)
  const [rows, setRows] = useState(30)
  const load = useCallback(async () => {
    const r = await fetch(`/api/games/${info.slug}/results?kind=godmode`, { cache: 'no-store' })
    const d = await r.json()
    setRes(d.result)
    setState(d.state)
  }, [info.slug])
  useEffect(() => { load() }, [load])
  const job = useJob('godmode', info.slug, load)
  const prog = job.job?.progress

  // промежуточные результаты появляются после каждой стадии
  const checkpointStage = prog?.type === 'checkpoint' ? prog.stage : null
  useEffect(() => { if (checkpointStage) load() }, [checkpointStage, load])

  const elapsed = Number(prog?.elapsed ?? 0)
  const budgetS = Number(prog?.budget ?? MAX_S)

  return (
    <section className="panel" data-testid="godmode">
      <p>
        Потиражный режим: для каждого тиража по порядку все модели делают прогноз только по предыдущим тиражам,
        результат сверяется с выпавшими числами. Прогноз даёт стратегия «лидер за всю историю»: на каждый тираж
        берётся модель, которая угадала больше всех за все предыдущие тиражи. Пул моделей расширяется (сетка
        параметров, бустинг, поиск комбинаций признаков), пока перебор не исчерпан — обычно минуты, — но не
        дольше 8 часов.
      </p>
      <div className="run-bar">
        {job.running
          ? <button className="btn btn-ghost" onClick={job.cancel} data-testid="stop-god">Остановить</button>
          : (
            <>
              <button className="btn" onClick={() => job.start({})} data-testid="run-god">
                {state?.resumable ? 'Начать заново' : 'Запустить режим Бога'}
              </button>
              {state?.resumable && !state.exhausted && (
                <button className="btn btn-ghost" onClick={() => job.start({ resume: true })} data-testid="resume-god">
                  Продолжить поиск
                </button>
              )}
            </>
          )}
      </div>
      {job.error && <p className="error">{job.error}</p>}
      {state?.resumable && !state.exhausted && !job.running && (
        <p className="muted small" data-testid="resume-note">
          Сохранено состояние: {state.experts} экспертов, {duration(state.elapsed)} работы. «Продолжить» не пересчитывает
          найденное и ищет дальше; при новых тиражах продолжение невозможно — только запуск заново.
        </p>
      )}
      {job.running && (
        <div className="god-progress" data-testid="god-progress">
          {job.job?.external && <p className="muted small">Запущено вне приложения (консоль или Планировщик) — показываю его прогресс.</p>}
          <div className="progress"><span style={{ width: `${Math.min(100, (elapsed / budgetS) * 100)}%` }} /></div>
          <p className="muted">
            {prog?.stage ?? 'Подготовка'}{prog?.note ? `: ${prog.note}` : ''}. Экспертов: {prog?.experts ?? 0}.
            Прошло {duration(elapsed)} (предел — {duration(budgetS)}).
          </p>
        </div>
      )}
      {job.job?.status === 'error' && <p className="error">Ошибка: {job.job.error}</p>}
      {job.job?.status === 'cancelled' && <p className="muted">Остановлено. Показан последний сохранённый результат.</p>}

      {res && <GodResultView r={res} info={info} rows={rows} setRows={setRows} />}
      {!res && !job.running && <p className="empty">Режим Бога ещё не запускался для этой игры.</p>}
    </section>
  )
}

function GodResultView({ r, info, rows, setRows }: { r: GodResult; info: Info; rows: number; setRows: (n: number) => void }) {
  const stale = info.last && r.last_draw_no !== info.last.no
  const strategies = [...r.strategies].sort((a, b) => b.first.mean_hits - a.first.mean_hits)
  return (
    <div data-testid="god-result">
      <p className="muted small">
        {r.complete ? (r.exhausted ? 'Завершено: перебор исчерпан' : 'Завершено (время вышло)') : `Промежуточный итог (стадия «${r.stage}»)`} {r.generated_at.replace('T', ' ')},
        экспертов: {r.experts}, время: {duration(r.elapsed_seconds)}.
        {stale && <span className="warn"> Появились новые тиражи — запустите заново.</span>}
      </p>
      <div className="callout">{r.verdict}</div>

      <div className="predict-card">
        <h3>Прогноз на тираж №{r.next.no}</h3>
        <p className="muted">Стратегия «{r.next.strategy}»{r.next.model ? `: больше всех за всю историю угадала модель «${r.next.model}»` : ''}</p>
        <BlockBalls blocks={r.next.numbers} size="lg" />
      </div>

      <h3>Мета-стратегии</h3>
      <p className="muted small">
        Прогноз даёт «лидер за всю историю» (выделен), остальные стратегии — для сравнения. Модели отбираются по первой
        половине (тиражи №{r.evaluation.from}–{r.evaluation.split - 1}), честный результат — вторая половина
        (№{r.evaluation.split}–{r.evaluation.to}). Случайный выбор: {num(r.baseline.mean)} за тираж.
        Активная модель менялась {r.switches} раз.
      </p>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Стратегия</th><th className="r">1-я половина</th><th className="r">к случайному</th><th className="r">2-я половина</th><th className="r">к случайному</th><th className="r">p</th></tr></thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.key} className={s.key === r.chosen ? 'best' : ''}>
                <td>{s.title}</td>
                <td className="r num">{num(s.first.mean_hits)}</td><td className="r num">{pct(s.first.excess_pct)}</td>
                <td className="r num">{num(s.second.mean_hits)}</td><td className="r num">{pct(s.second.excess_pct)}</td>
                <td className="r num">{pval(s.second.p_better)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Для сравнения: случайные «эксперты» на второй половине отклоняются от ожидания на{' '}
        {r.random_control_excess.map((v) => (v >= 0 ? '+' : '') + num(v)).join(', ')} числа за тираж — это масштаб шума.
      </p>

      <LineChart series={[
        { name: `Стратегия: ${r.chosen_title}`, values: r.curves.chosen, color: 'var(--accent)' },
        { name: `Лучшая модель 1-й половины: ${r.best_expert.title}`, values: r.curves.best_expert, color: 'var(--ball-dark)' },
        { name: 'Случайный выбор', values: r.curves.random, color: 'var(--muted)', dashed: true },
      ]} />

      <h3>Потиражная лента</h3>
      <div className="table-wrap">
        <table className="data" data-testid="timeline">
          <thead><tr><th>Тираж</th><th>Прогноз</th><th>Выпало</th><th className="r">Угадано</th><th>Модель</th></tr></thead>
          <tbody>
            {r.timeline.slice(0, rows).map((t) => (
              <tr key={t.no}>
                <td>№{t.no}<span className="sub">{t.date}</span></td>
                <td><BlockBalls blocks={t.predicted} actual={t.actual} size="sm" /></td>
                <td><BlockBalls blocks={t.actual} tone="actual" size="sm" /></td>
                <td className="r num">{t.hits}</td>
                <td className="small">{t.model ?? 'голосование'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows < r.timeline.length && <button className="link-btn" onClick={() => setRows(r.timeline.length)}>Показать {r.timeline.length} тиражей</button>}

      <h3>Лучшие модели по первой половине</h3>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Модель</th><th className="r">1-я половина</th><th className="r">2-я половина</th><th className="r">к случайному</th></tr></thead>
          <tbody>
            {r.top_experts.map((x) => (
              <tr key={x.key}><td>{x.title}</td><td className="r num">{num(x.first.mean_hits)}</td><td className="r num">{num(x.second.mean_hits)}</td><td className="r num">{pct(x.second.excess_pct)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
