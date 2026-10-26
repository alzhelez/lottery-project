'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { nf } from './format'
import { useJob } from './useJob'

interface Row { g1: number | null; g2: number | null; prize: number; superprize: boolean; percent: number | null }
interface Rules {
  fetched_at: string
  how: string
  schedule: { lototron: boolean; rng: boolean; times: Record<string, 'L' | 'R'> }
  faq: Array<{ question: string; answer: string }>
  cards: Array<{ title: string; text: string }>
  table: Row[]
  table_error: string | null
  min_prize: number | null
  next_draw: {
    number: number | null; date: string | null; super_prize: number | null; price: number | null
    lototron: boolean | null; prize_fund_pct: number | null; jackpot_guaranteed: number | null
  } | null
}
interface NextDraw { number: number; return: number; return_without_super: number; usual_return: number | null; verdict: string }

const rub = (v: number) => `${nf.format(Math.round(v))} ₽`

function guess(r: Row): string {
  if (r.g1 == null) return '—'
  if (r.g2 == null) return String(r.g1)
  return `${r.g1} + ${r.g2}`
}

/** «Как проходят розыгрыши» и таблица выигрышей со stoloto.ru/<игра>/rules. */
export function RulesPanel({ slug, stolotoUrl, lastNo }: { slug: string; stolotoUrl: string; lastNo?: number | null }) {
  const [rules, setRules] = useState<Rules | null>(null)
  const [next, setNext] = useState<NextDraw | null>(null)
  const [loaded, setLoaded] = useState(false)
  const load = useCallback(async () => {
    const d = await fetch(`/api/games/${slug}/rules`, { cache: 'no-store' }).then((r) => r.json())
    setRules(d.rules)
    setNext(d.nextDraw)
    setLoaded(true)
  }, [slug])
  useEffect(() => { load() }, [load])
  const job = useJob('rules', slug, load)
  // данные о ближайшем тираже обновляются в каждом цикле автозапуска (раз в час), а у быстрых
  // игр тираж проходит за минуты — если он уже сыгран, обновляем сами (один раз за открытие)
  const refreshed = useRef(false)
  const staleNext = rules?.next_draw?.number != null && lastNo != null && rules.next_draw.number <= lastNo
  useEffect(() => {
    if (staleNext && !refreshed.current && !job.running) {
      refreshed.current = true
      job.start()
    }
  }, [staleNext, job])

  if (!loaded) return null
  const nd = rules?.next_draw
  const kinds = rules ? [rules.schedule.lototron && 'лототрон', rules.schedule.rng && 'генератор случайных чисел (ГСЧ)'].filter(Boolean) : []
  const paragraphs = (rules?.how ?? '').split('\n').filter(Boolean)
  return (
    <section className="panel" data-testid="rules">
      <div className="run-bar">
        <button className="btn btn-ghost" onClick={() => job.start()} disabled={job.running} data-testid="refresh-rules">
          {job.running ? 'Загружаю правила…' : 'Обновить правила'}
        </button>
        {rules && <span className="muted small">Загружено {rules.fetched_at.replace('T', ' ').slice(0, 16)} с <a href={`${stolotoUrl.replace(/game\/?$/, '')}rules`} target="_blank" rel="noreferrer">stoloto.ru</a></span>}
        {job.job?.status === 'error' && <span className="error">Ошибка: {job.job.error}</span>}
      </div>
      {!rules ? (
        <p className="empty">Правила ещё не загружены — нажмите «Обновить правила» (или выполните <code>lp.bat rules</code>).</p>
      ) : (
        <>
          {nd && (
            <dl className="facts">
              <div><dt>Ближайший тираж</dt><dd>№{nd.number}</dd>
                {staleNext && <dd className="sub warn" data-testid="rules-stale">{job.running ? 'уже сыгран — обновляю…' : 'уже сыгран — обновите правила, чтобы увидеть текущий'}</dd>}
                <dd className="sub">{nd.date?.replace('T', ' ').slice(0, 16)}{nd.lototron != null && ` · ${nd.lototron ? 'лототрон (трансляция)' : 'без трансляции'}`}</dd></div>
              <div><dt>Суперприз</dt><dd data-testid="rules-superprize">{nd.super_prize ? rub(nd.super_prize) : '—'}</dd>
                <dd className="sub">{nd.jackpot_guaranteed ? `гарантированный минимум ${rub(nd.jackpot_guaranteed)}` : ''}</dd></div>
              <div><dt>Ставка и призовой фонд</dt><dd>{nd.price ? rub(nd.price) : '—'}</dd>
                <dd className="sub">{nd.prize_fund_pct ? `в призы уходит ${nd.prize_fund_pct}% выручки` : ''}</dd></div>
              {next && <div><dt>Ожидаемый возврат тиража</dt><dd data-testid="rules-return">{next.return.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</dd>
                <dd className="sub">без суперприза {next.return_without_super.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</dd></div>}
            </dl>
          )}
          {next && <p className={next.return >= 1 ? 'callout' : 'muted small'}>{next.verdict}</p>}

          <h3>Как проходят розыгрыши</h3>
          {paragraphs.length ? paragraphs.map((p, i) => <p key={i}>{p}</p>) : <p className="muted">На stoloto.ru для этой игры текста нет.</p>}
          {kinds.length > 0 && (
            <p className="muted small" data-testid="rules-mechanism">
              Способ розыгрыша: {kinds.join(' и ')}.
              {rules.schedule.lototron && rules.schedule.rng && ' Программа проверяет тиражи каждого способа отдельно (вкладка «Обзор»).'}
            </p>
          )}

          <h3>Таблица выигрышей</h3>
          {rules.table.length ? (
            <div className="table-wrap">
              <table className="data" data-testid="rules-table">
                <thead><tr><th>Совпадения</th><th className="r">Выигрыш</th></tr></thead>
                <tbody>
                  {rules.table.map((r, i) => (
                    <tr key={i}>
                      <td className="num">{guess(r)}</td>
                      <td className="r num">{r.superprize ? 'Суперприз' : r.prize > 0 ? rub(r.prize) : r.percent ? `${r.percent.toLocaleString('ru-RU')}% призового фонда` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">{rules.table_error ? 'Таблицы выигрышей в API нет (у бинго призы зависят от туров) — шансы туров по архиву на вкладке «Шансы».' : 'Таблица не загружена.'}</p>
          )}
          <p className="muted small">
            «a + b» — совпало чисел в первом и втором поле (или в поле и бонусе). Доля призового фонда делится
            между всеми победителями категории; фиксированный выигрыш платится каждому.
          </p>

          {(rules.faq.length > 0 || rules.cards.length > 0) && <h3>Призовой фонд и суперприз</h3>}
          {rules.cards.length > 0 && (
            <ul className="plain">{rules.cards.map((c, i) => <li key={i}><b>{c.title}:</b> {c.text}</li>)}</ul>
          )}
          {rules.faq.map((q, i) => (
            <details key={i} className="faq"><summary>{q.question}</summary>{q.answer.split('\n').map((p, j) => <p key={j}>{p}</p>)}</details>
          ))}
        </>
      )}
    </section>
  )
}
