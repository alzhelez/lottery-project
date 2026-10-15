'use client'
import { useState } from 'react'
import { Balls, BlockBalls } from './Balls'
import { FreqBars, LineChart } from './Charts'
import type { ChaosResult } from './ChaosPanel'
import { nf, num, pct, pval } from './format'

interface Metric { n: number; mean_hits: number; baseline: number; excess: number; excess_pct: number; z: number; p_better: number; p_adjusted?: number }
interface Money { n: number; won?: number; spent?: number; return?: number; random_return?: number; excess_pct?: number }
interface ModelRow {
  key: string; title: string; family: string; control: boolean; selection: Metric; holdout: Metric; all: Metric; curve: number[]; next: number[][]
  money?: { selection: Money; holdout: Money } | null
}
interface Test { block: string; title: string; p_value: number; p_adjusted: number; significant: boolean; detail: string; exploitable: boolean }

export interface Analysis {
  generated_at: string
  last_draw_no: number
  format: string
  seconds: number
  randomness: {
    status: string; verdict: string; level: string; tests: Test[]; q_value?: number
    unreplicated?: string[]
    detectable?: Array<{ block: string; draws: number; relative_pct: number; text: string }>
    mechanisms?: MechReport
  }
  drift?: { verdict: string; alarms: Array<{ title: string; block: string; check: string; p_adjusted: number; detail: string }>; checks: unknown[] }
  chaos?: ChaosResult
  popularity?: { available: boolean; significant?: boolean; verdict?: string; reason?: string; p_value?: number; draws?: number }
  descriptive: Array<{ block: string; numbers: number[]; frequency: number[]; recent100: number[]; gap: number[]; expected: number; expected_recent: number; count: number }>
  evaluation: {
    status: string
    message?: string
    draws: number
    test: { from: number; split: number; to: number; selection_draws: number; holdout_draws: number }
    baseline: { mean: number; sd: number }
    models: ModelRow[]
    best_key: string
    conclusion: string
    recent: Array<{ no: number; date: string; actual: number[][]; best: number[][]; best_hits: number; consensus: number[][]; consensus_hits: number }>
    next_votes: Array<{ block: string; models: number; votes: Array<{ number: number; votes: number }> }>
    next_prediction: { model: string; numbers: number[][] }
    money?: { available: boolean; reason?: string; price?: number; price_source?: string; draws_with_prizes?: number } | null
    detectable_edge_pct?: number | null
    by_mechanism?: Record<string, { title: string; draws: number; baseline: { mean: number }; conclusion?: string
      best: { title: string; selection: { excess_pct: number; mean_hits: number }; holdout: { excess_pct: number; mean_hits: number; p_adjusted?: number } } | null }>
    distribution: { observed: number[]; expected: number[] }
  }
}

interface MechReport {
  counts: { L: number; R: number; unknown: number }
  mixed: boolean
  by_mechanism: Record<string, { title: string; draws: number; verdict: string; level: string; significant: Test[] }>
  comparison: Array<{ block: string; p_value: number; detail: string }>
  order: Record<string, { verdict: string; significant: Array<{ block: string; position: number; p_adjusted: number; detail: string; replicated?: boolean }> }>
}

const MECH: Record<string, string> = { L: 'Лототрон', R: 'ГСЧ' }

/** Лототрон и ГСЧ отдельно, сравнение между ними и порядок выпадения шаров. */
function Mechanisms({ m }: { m: MechReport }) {
  const kinds = Object.keys(m.by_mechanism)
  if (!kinds.length) return null
  return (
    <section data-testid="mechanisms">
      <h3>Лототрон и ГСЧ</h3>
      <p className="muted small">
        Тиражи разделены по способу проведения: по видеозаписи трансляции в ответе API и по расписанию из правил игры
        (лототрон: {nf.format(m.counts.L)}, ГСЧ: {nf.format(m.counts.R)}{m.counts.unknown ? `, не определено: ${nf.format(m.counts.unknown)}` : ''}).
        Физический лототрон теоретически может давать перекосы (износ шаров, порядок загрузки), ГСЧ — только при ошибке.
      </p>
      <div className="mech-grid">
        {kinds.map((k) => {
          const b = m.by_mechanism[k]
          const o = m.order[k]
          return (
            <div key={k} className={`mech-card callout lv-${b.level}`}>
              <h4>{MECH[k]} — {nf.format(b.draws)} тиражей</h4>
              <div>{b.verdict}</div>
              {o && <div className="small">Порядок шаров: {o.verdict}.{o.significant.length > 0 && ' ' + o.significant.slice(0, 2).map((t) => `${t.block}, шар ${t.position}: ${t.detail}${t.replicated ? '' : ' (не повторилось)'}`).join('; ')}</div>}
            </div>
          )
        })}
      </div>
      {m.comparison.length > 0 && (
        <p className="small">Совпадают ли частоты чисел у лототрона и ГСЧ: {m.comparison.map((c) => `${c.block} — ${c.detail}`).join('; ')}.
          {m.comparison.every((c) => c.p_value >= 0.05) ? ' Разницы нет.' : ' Есть разница — проверьте, повторится ли она.'}</p>
      )}
    </section>
  )
}

const LEVEL_TEXT: Record<string, string> = { random: 'Случайная', weak: 'Отклонения без пользы', signal: 'Есть отклонения', na: '—' }

export function AnalysisOverview({ a }: { a: Analysis }) {
  const r = a.randomness
  const [recent, setRecent] = useState(false)
  return (
    <section className="panel" data-testid="overview">
      <p className="format">Формат: {a.format}</p>
      <div className={`callout lv-${r.level}`}>
        <strong>{LEVEL_TEXT[r.level] ?? r.level}.</strong> {r.verdict}
      </div>
      {r.tests.length > 0 && (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>Блок</th><th>Проверка</th><th>Что получилось</th><th className="r">p</th><th className="r">p с поправкой</th></tr>
            </thead>
            <tbody>
              {r.tests.map((t, i) => (
                <tr key={i} className={t.significant ? 'sig' : ''}>
                  <td>{t.block}</td><td>{t.title}</td><td className="detail">{t.detail}</td>
                  <td className="r num">{pval(t.p_value)}</td><td className="r num">{pval(t.p_adjusted)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small">
        p — вероятность увидеть такое же или большее отклонение у честной лотереи. Поправка Холма учитывает,
        что проверок много: значимым считается p с поправкой ниже 0,05 — и только если отклонение повторилось
        во второй половине истории.
        {r.unreplicated && r.unreplicated.length > 0 && ` Не повторилось (шум): ${r.unreplicated.join(', ').toLowerCase()}.`}
      </p>
      {r.detectable && r.detectable.length > 0 && (
        <div className="callout" data-testid="detectable">
          <strong>Что уже исключено.</strong> {r.detectable.map((d) => d.text).join('. ')}. Меньшие перекосы при таком
          объёме архива не отличить от случайности — и пользы для прогноза от них почти нет.
        </div>
      )}
      {a.drift && (
        <div className={`callout ${a.drift.alarms.length ? 'lv-signal' : 'lv-random'}`} data-testid="drift">
          <strong>Наблюдение за дрейфом.</strong> {a.drift.verdict}
          <span className="sub">Последние тиражи каждого способа сравниваются с честной лотереей и с прошлой историей; о новой тревоге приходит уведомление в Telegram.</span>
        </div>
      )}
      {r.mechanisms && <Mechanisms m={r.mechanisms} />}
      {a.popularity?.available && (
        <div className={`callout ${a.popularity.significant ? 'lv-signal' : ''}`} data-testid="popularity">
          <strong>Популярность чисел у игроков.</strong> {a.popularity.verdict}
          <span className="sub">По числу победителей в {a.popularity.draws} тиражах архива.</span>
        </div>
      )}
      <h3>Частоты чисел</h3>
      <label className="check">
        <input type="checkbox" checked={recent} onChange={(e) => setRecent(e.target.checked)} /> только последние 100 тиражей
      </label>
      {a.descriptive.map((d) => (
        <FreqBars key={d.block} numbers={d.numbers} values={recent ? d.recent100 : d.frequency}
          expected={recent ? d.expected_recent : d.expected}
          title={`${d.block}: сколько раз выпало каждое число (пунктир — ожидание при честной лотерее)`} />
      ))}
    </section>
  )
}

export function AnalysisMethods({ a, nextNo }: { a: Analysis; nextNo: number | null }) {
  const e = a.evaluation
  const [showAll, setShowAll] = useState(false)
  if (e.status !== 'ok') return <p className="empty">{e.message}</p>
  const models = [...e.models].sort((x, y) => y.selection.mean_hits - x.selection.mean_hits)
  const best = e.models.find((m) => m.key === e.best_key)!
  const cons = e.models.find((m) => m.key === 'consensus')
  const ctrl = e.models.find((m) => m.control)
  const money = e.money?.available ? e.money : null
  const shown = showAll ? models : models.slice(0, 10)
  return (
    <section className="panel" data-testid="methods">
      <div className="callout">{e.conclusion}</div>

      <div className="predict-card" data-testid="methods-prediction">
        <h3>Прогноз на тираж №{nextNo}</h3>
        <p className="muted">Метод, лучший на отрезке отбора: «{e.next_prediction.model}»</p>
        <BlockBalls blocks={e.next_prediction.numbers} size="lg" />
        <h4>Наиболее часто повторяющиеся предсказания</h4>
        <p className="muted small">Сколько из {e.next_votes[0]?.models} методов включили число в прогноз на следующий тираж.</p>
        {e.next_votes.map((b) => (
          <div key={b.block} className="votes">
            <span className="votes-block">{b.block}</span>
            {b.votes.slice(0, 12).map((v) => (
              <span key={v.number} className="vote"><Balls numbers={[v.number]} size="sm" tone="plain" /><span className="vote-n">{v.votes}</span></span>
            ))}
          </div>
        ))}
      </div>

      <h3>Как методы угадывали на истории</h3>
      <p className="muted small">
        Каждый тираж прогнозировался только по предыдущим. Отбор — тиражи №{e.test.from}–{e.test.split - 1}{' '}
        ({nf.format(e.test.selection_draws)}), контроль — №{e.test.split}–{e.test.to} ({nf.format(e.test.holdout_draws)}).
        Случайный выбор угадывает в среднем {num(e.baseline.mean)} чисел за тираж.
      </p>
      <div className="table-wrap">
        <table className="data" data-testid="models-table">
          <thead>
            <tr>
              <th>Метод</th>
              <th className="r">Отбор: угадано</th><th className="r">к случайному</th>
              <th className="r">Контроль: угадано</th><th className="r">к случайному</th><th className="r">p с поправкой</th>
              {money && <th className="r" title="Выигрыш по реальным выплатам на рубль ставки, контрольный отрезок">Контроль: ₽ на рубль</th>}
            </tr>
          </thead>
          <tbody>
            {shown.map((m) => (
              <tr key={m.key} className={m.key === e.best_key ? 'best' : m.control ? 'control' : ''}>
                <td>{m.title}</td>
                <td className="r num">{num(m.selection.mean_hits)}</td><td className="r num">{pct(m.selection.excess_pct)}</td>
                <td className="r num">{num(m.holdout.mean_hits)}</td><td className="r num">{pct(m.holdout.excess_pct)}</td>
                <td className="r num">{m.control ? '—' : pval(m.holdout.p_adjusted)}</td>
                {money && <td className="r num">{m.money?.holdout.return != null ? num(m.money.holdout.return, 3) : '—'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {models.length > 10 && (
        <button className="link-btn" onClick={() => setShowAll((v) => !v)}>{showAll ? 'Свернуть' : `Показать все методы (${models.length})`}</button>
      )}

      {money && ctrl?.money && (
        <p className="muted small" data-testid="money-note">
          ₽ на рубль — сколько выиграл бы билет с прогнозом метода по реальным выплатам этих тиражей (цена билета
          {' '}{money.price} ₽, {money.price_source}; тиражей с выплатами: {money.draws_with_prizes}). Случайный билет на том же
          отрезке в среднем возвращает {num(ctrl.money.holdout.random_return, 3)}. Крупные призы редки, поэтому эта
          оценка шумнее, чем по угаданным числам.
        </p>
      )}
      {e.money && !e.money.available && <p className="muted small">{e.money.reason}</p>}

      {e.detectable_edge_pct != null && (
        <p className="callout" data-testid="method-edge">
          <strong>Что исключено.</strong> На контрольном отрезке ({nf.format(e.test.holdout_draws)} тиражей) метод,
          угадывающий хотя бы на {e.detectable_edge_pct.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}% больше
          случайного выбора, был бы виден с вероятностью 80%. Методов с таким преимуществом не найдено.
        </p>
      )}

      {e.by_mechanism && Object.keys(e.by_mechanism).length > 0 && (
        <>
          <h3>Лототрон и ГСЧ отдельно</h3>
          <p className="muted small">Все методы заново проверены только на тиражах одного способа — на случай, если закономерность есть у лототрона, но размывается тиражами ГСЧ.</p>
          <div className="table-wrap">
            <table className="data" data-testid="methods-by-mechanism">
              <thead><tr><th>Способ</th><th className="r">Тиражей</th><th>Лучший на отборе</th><th className="r">Контроль: к случайному</th><th className="r">p с поправкой</th></tr></thead>
              <tbody>
                {Object.entries(e.by_mechanism).map(([k, m]) => (
                  <tr key={k}>
                    <td>{m.title}</td><td className="r num">{nf.format(m.draws)}</td>
                    <td>{m.best?.title ?? '—'}</td>
                    <td className="r num">{m.best ? pct(m.best.holdout.excess_pct) : '—'}</td>
                    <td className="r num">{m.best ? pval(m.best.holdout.p_adjusted) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Накопленное превышение над случайным выбором</h3>
      <p className="muted small">Сумма (угадано − {num(e.baseline.mean, 2)}) по тиражам. Линия, которая блуждает около нуля, — это удача, а не закономерность.</p>
      <LineChart series={[
        { name: best.title, values: best.curve, color: 'var(--accent)' },
        ...(cons ? [{ name: cons.title, values: cons.curve, color: 'var(--ball-dark)' }] : []),
        ...(ctrl ? [{ name: ctrl.title, values: ctrl.curve, color: 'var(--muted)', dashed: true }] : []),
      ]} />

      <h3>Распределение угаданных у лучшего метода</h3>
      <div className="table-wrap">
        <table className="data compact">
          <thead><tr><th>Угадано</th>{e.distribution.observed.map((_, i) => <th key={i} className="r">{i}</th>)}</tr></thead>
          <tbody>
            <tr><td>Фактически</td>{e.distribution.observed.map((v, i) => <td key={i} className="r num">{nf.format(v)}</td>)}</tr>
            <tr><td>Ожидание для случайного</td>{e.distribution.expected.map((v, i) => <td key={i} className="r num">{nf.format(Math.round(v))}</td>)}</tr>
          </tbody>
        </table>
      </div>

      <h3>Последние тиражи</h3>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Тираж</th><th>Выпало</th><th>Лучший метод</th><th className="r">Угадано</th><th>Консенсус</th><th className="r">Угадано</th></tr></thead>
          <tbody>
            {e.recent.map((d) => (
              <tr key={d.no}>
                <td>№{d.no}<span className="sub">{d.date}</span></td>
                <td><BlockBalls blocks={d.actual} tone="actual" size="sm" /></td>
                <td><BlockBalls blocks={d.best} actual={d.actual} size="sm" /></td>
                <td className="r num">{d.best_hits}</td>
                <td><BlockBalls blocks={d.consensus} actual={d.actual} size="sm" /></td>
                <td className="r num">{d.consensus_hits}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
