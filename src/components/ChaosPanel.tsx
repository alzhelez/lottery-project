'use client'
import { useState } from 'react'
import { BlockBalls } from './Balls'
import { nf, num, pct, pval } from './format'
import { useJob } from './useJob'

interface Metric { n: number; mean_hits: number; baseline: number; excess_pct: number; p_better: number; p_adjusted?: number }
interface ModelRow { key: string; title: string; family: string; control: boolean; selection: Metric; holdout: Metric }
interface Check {
  block: string; test: string; title: string; p_value: number; p_adjusted: number; value: number
  detail: string; replicated: boolean | null; significant: boolean
}
interface Group {
  key: string; title: string; draws: number; checks: Check[]; verdict: string
  evaluation: {
    status: string; message?: string; models: ModelRow[]; best_key: string; conclusion: string
    test: { from: number; split: number; to: number; selection_draws: number; holdout_draws: number }
    baseline: { mean: number }
  }
}
export interface ChaosResult {
  groups: Record<string, Group>
  next: { draw_no: number; mechanism: string | null; title?: string; reason: string; model?: string; numbers: number[][] | null; consensus?: number[][] }
  conclusion: string
  max_draws: number
}

const TITLE: Record<string, string> = { L: 'Лототрон', R: 'ГСЧ', all: 'Все тиражи' }

function Methods({ g }: { g: Group }) {
  const e = g.evaluation
  if (e.status !== 'ok') return <p className="muted">{e.message}</p>
  const rows = [...e.models].sort((a, b) => b.selection.mean_hits - a.selection.mean_hits)
  return (
    <>
      <p className="muted small">
        Отбор — тиражи №{e.test.from}–{e.test.split - 1} ({nf.format(e.test.selection_draws)}), контроль —
        №{e.test.split}–{e.test.to} ({nf.format(e.test.holdout_draws)}); только тиражи способа «{g.title}».
        Случайный выбор угадывает в среднем {num(e.baseline.mean)}.
      </p>
      <div className="table-wrap">
        <table className="data" data-testid={`chaos-methods-${g.key}`}>
          <thead><tr><th>Метод</th><th className="r">Отбор: к случайному</th><th className="r">Контроль: угадано</th><th className="r">к случайному</th><th className="r">p с поправкой</th></tr></thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.key} className={m.key === e.best_key ? 'best' : m.control ? 'control' : ''}>
                <td>{m.title}</td>
                <td className="r num">{pct(m.selection.excess_pct)}</td>
                <td className="r num">{num(m.holdout.mean_hits)}</td>
                <td className="r num">{pct(m.holdout.excess_pct)}</td>
                <td className="r num">{m.control ? '—' : pval(m.holdout.p_adjusted)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">{e.conclusion}</p>
    </>
  )
}

/** «Порядок из хаоса»: динамика тиражей отдельно по лототрону и ГСЧ. */
export function ChaosPanel({ slug, chaos, loaded, onDone }: { slug: string; chaos?: ChaosResult; loaded: boolean; onDone: () => void }) {
  const job = useJob('chaos', slug, onDone)
  const [about, setAbout] = useState(false)
  const n = chaos?.next
  return (
    <section className="panel" data-testid="chaos">
      <div className="run-bar">
        <button className="btn btn-ghost" onClick={() => job.start()} disabled={job.running} data-testid="run-chaos">
          {job.running ? 'Считаю…' : chaos ? 'Пересчитать только этот раздел' : 'Рассчитать'}
        </button>
        {job.running && job.job?.progress?.model && <span className="muted">{job.job.progress.model}</span>}
        {job.job?.status === 'error' && <span className="error">Ошибка: {job.job.error}</span>}
      </div>

      <p className="muted">
        Прогноз не по частоте чисел, а по динамике: если за кажущимся хаосом стоит порядок, похожие состояния
        в прошлом подсказывают, что будет дальше. Хаос у каждого способа розыгрыша свой, поэтому тиражи лототрона и
        тиражи ГСЧ разбираются отдельно, а прогноз на следующий тираж берётся из набора его способа.{' '}
        <button className="link-btn" onClick={() => setAbout((v) => !v)}>{about ? 'Скрыть' : 'Как это устроено'}</button>
      </p>
      {about && (
        <div className="callout" data-testid="chaos-about">
          <p><b>Состояние тиража</b> — среднее выпавшее число, размах, доля нечётных, доля малых чисел и сколько чисел
            повторилось из прошлого тиража.</p>
          <ul className="plain">
            <li><b>Аналоги</b> (метод Лоренца) — в прошлом ищутся моменты, когда последние один-два тиража были
              больше всего похожи на нынешние, и берётся, что выпало после них.</li>
            <li><b>Фазовое пространство</b> (теорема Такенса) — состояния нескольких последних тиражей образуют точку;
              прогноз — что выпадало после ближайших точек. Симплекс-прогноз Сугихары–Мэя — то же с E+1 соседями.</li>
            <li><b>Порядковые паттерны</b> (Бандт–Помпе) — «узор» подъёмов и спадов среднего числа за 3–4 тиража и что
              выпадало после такого же узора.</li>
          </ul>
          <p>Проверки «есть ли порядок»: нелинейная предсказуемость (корреляция симплекс-прогноза с фактом), энтропия
            порядковых паттернов и детерминизм рекуррентного анализа — против перемешанных копий тех же тиражей, у
            которых динамики нет по построению. Находка засчитывается, если повторяется в обеих половинах истории.
            Методы проверяются как остальные: отбор, контроль, сравнение со случайным выбором. Для быстрых игр
            берутся последние {nf.format(chaos?.max_draws ?? 20000)} тиражей каждого способа.</p>
        </div>
      )}

      {!chaos ? (
        loaded && <p className="empty">Раздел ещё не рассчитан — нажмите «Рассчитать» или запустите полный анализ.</p>
      ) : (
        <>
          <div className="callout" data-testid="chaos-conclusion">{chaos.conclusion}</div>

          <div className="predict-card" data-testid="chaos-prediction">
            <h3>Прогноз на тираж №{n?.draw_no}{n?.title ? ` — ${n.title}` : ''}</h3>
            <p className="muted">{n?.reason}</p>
            {n?.numbers ? (
              <>
                <p className="muted">Метод, лучший на отборе для этого способа: «{n.model}»</p>
                <BlockBalls blocks={n.numbers} size="lg" />
                {n.consensus && (
                  <>
                    <h4>Консенсус методов хаоса</h4>
                    <BlockBalls blocks={n.consensus} size="sm" />
                  </>
                )}
                <p className="muted small">Прогноз записан в журнал («Порядок из хаоса») и будет сверен с тиражом.</p>
              </>
            ) : <p>Прогноза нет: для этого способа мало тиражей.</p>}
          </div>

          <div className="mech-grid">
            {Object.values(chaos.groups).map((g) => {
              const found = g.checks.some((c) => c.significant)
              return (
                <div key={g.key} className="mech-card" data-testid={`chaos-group-${g.key}`}>
                  <h4>{TITLE[g.key] ?? g.title} — {nf.format(g.draws)} тиражей</h4>
                  <span className={`verdict ${found ? 'lv-signal' : 'lv-random'}`}>{found ? 'порядок найден' : 'порядка нет'}</span>
                  <p className="small">{g.verdict}</p>
                </div>
              )
            })}
          </div>

          {Object.values(chaos.groups).map((g) => (
            <div key={g.key}>
              <h3>{TITLE[g.key] ?? g.title}: есть ли порядок</h3>
              <div className="table-wrap">
                <table className="data" data-testid={`chaos-checks-${g.key}`}>
                  <thead><tr><th>Проверка</th><th>Поле</th><th>Результат</th><th className="r">p с поправкой</th><th>Повторяется</th></tr></thead>
                  <tbody>
                    {g.checks.map((c, i) => (
                      <tr key={i} className={c.significant ? 'sig' : ''}>
                        <td>{c.title}</td><td>{c.block}</td><td className="small">{c.detail}</td>
                        <td className="r num">{pval(c.p_adjusted)}</td>
                        <td>{c.replicated == null ? '—' : c.replicated ? 'да' : 'нет'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3>{TITLE[g.key] ?? g.title}: методы хаоса на истории</h3>
              <Methods g={g} />
            </div>
          ))}
        </>
      )}
    </section>
  )
}
