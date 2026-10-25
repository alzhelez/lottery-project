'use client'
import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { nf, num, pct, pval } from './format'
import { useJob } from './useJob'

interface GameState {
  title: string; draws: number; status: 'queued' | 'running' | 'done' | 'error'
  from_no?: number; to_no?: number; seconds?: number; experts?: number; exhausted?: boolean
  mean_hits?: number; baseline?: number; excess_pct?: number; p_better?: number; error?: string; stage?: string
  progress?: { stage?: string; done?: number; total?: number; experts?: number; total_elapsed?: number; note?: string }
}
interface State {
  started_at: string; finished_at: string | null; from: number; budget: number
  status: 'running' | 'done' | 'stopped'; order: string[]; games: Record<string, GameState>; skipped: Record<string, string>
  current?: string | null
}

const STATUS: Record<GameState['status'], string> = { queued: 'в очереди', running: 'идёт', done: 'готово', error: 'ошибка' }
const when = (s?: string | null) => (s ? s.replace('T', ' ').slice(0, 16) : '')

function dur(sec?: number): string {
  if (sec == null) return '—'
  const h = Math.floor(sec / 3600)
  const m = Math.round((sec % 3600) / 60)
  return h ? `${h} ч ${m} мин` : `${m} мин`
}

/** «Всеобъемлющий режим Бога»: все игры по очереди, проверка экспертов на каждом тираже с 1000-го. */
export function GodModeAll() {
  const [data, setData] = useState<{ state: State | null; running: boolean } | null>(null)
  const [showSkipped, setShowSkipped] = useState(false)
  const load = useCallback(async () => {
    try {
      setData(await (await fetch('/api/godmode-all', { cache: 'no-store' })).json())
    } catch { /* сервер перезапускается */ }
  }, [])
  const job = useJob('godmode_all', null, () => load())
  const running = job.running || !!data?.running
  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!running) return
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [running, load])

  const st = data?.state
  const games = st ? st.order.map((s) => ({ slug: s, ...st.games[s] })) : []
  const done = games.filter((g) => g.status === 'done').length
  const cur = st?.current ? st.games[st.current] : null
  const live = job.job?.progress && job.job.progress.game === st?.current ? job.job.progress : cur?.progress

  async function start(resume: boolean) {
    if (!resume && !window.confirm('Запустить всеобъемлющий режим Бога заново? Проход по всем играм займёт от нескольких часов до суток; прошлые итоги прохода будут заменены.')) return
    await job.start({ resume })
    setTimeout(load, 1500)
  }

  return (
    <section className="god-all" data-testid="godmode-all">
      <h2>Всеобъемлющий режим Бога</h2>
      <p className="note">
        Все игры по очереди, от коротких архивов к длинным. В каждой эксперты проверяются на каждом тираже начиная
        с 1000-го и до последнего — каждый тираж только по предыдущим, без ограничения длины истории. До 8 часов на
        игру; весь проход — от нескольких часов до суток. Пока он идёт, автозапуск не запускает свой режим Бога, а
        прогноз «Б» в журнал пишет этот проход. Остановленный проход можно продолжить: готовые игры не пересчитываются.
      </p>
      <div className="run-bar">
        {!running && (
          st && st.status === 'stopped' ? (
            <>
              <button className="btn" onClick={() => start(true)} data-testid="godmode-all-resume">Продолжить проход</button>
              <button className="btn btn-ghost" onClick={() => start(false)}>Начать заново</button>
            </>
          ) : (
            <button className="btn" onClick={() => start(false)} data-testid="godmode-all-start">
              {st ? 'Запустить заново' : 'Всеобъемлющий режим Бога'}
            </button>
          )
        )}
        {running && <button className="btn btn-danger" onClick={() => job.cancel()} data-testid="godmode-all-stop">Остановить</button>}
        {job.error && <span className="error">{job.error}</span>}
        {job.job?.status === 'error' && <span className="error">Ошибка: {job.job.error}</span>}
      </div>

      {st && (
        <>
          <p className="small" data-testid="godmode-all-status">
            {st.status === 'done' ? `Проход завершён ${when(st.finished_at)}` : running ? 'Идёт' : 'Остановлен'}: готово
            {' '}{done} из {games.length} игр, начат {when(st.started_at)}.
          </p>
          {running && cur && (
            <div className="now small" data-testid="godmode-all-current">
              <b>{cur.title}</b>: {live?.stage ?? cur.stage ?? 'подготовка'}{live?.note ? ` — ${live.note}` : ''}
              {live?.experts != null && <>, экспертов {nf.format(live.experts)}</>}
              {live?.total_elapsed != null && <>, идёт {dur(live.total_elapsed)}</>}
            </div>
          )}
          <div className="table-wrap">
            <table className="data compact" data-testid="godmode-all-table">
              <thead>
                <tr>
                  <th>Игра</th><th className="r">Тиражей</th><th>Проверка</th><th>Статус</th><th className="r">Время</th>
                  <th className="r">Угадано</th><th className="r">Случайный</th><th className="r">Разница</th><th className="r">p</th>
                </tr>
              </thead>
              <tbody>
                {games.map((g) => (
                  <tr key={g.slug} className={g.status === 'done' && (g.p_better ?? 1) < 0.05 ? 'sig' : ''}>
                    <td><Link href={`/games/${g.slug}`}>{g.title}</Link></td>
                    <td className="r num">{nf.format(g.draws)}</td>
                    <td className="num small">{g.from_no ? `№${g.from_no}–${g.to_no}` : '—'}</td>
                    <td>
                      <span className={`status-tag st-${g.status}`}>{STATUS[g.status]}</span>
                      {g.error && <span className="sub error">{g.error}</span>}
                      {g.status === 'done' && g.exhausted === false && <span className="sub">остановлен по времени</span>}
                    </td>
                    <td className="r num">{dur(g.seconds)}</td>
                    <td className="r num">{num(g.mean_hits)}</td>
                    <td className="r num">{num(g.baseline)}</td>
                    <td className="r num">{pct(g.excess_pct)}</td>
                    <td className="r num">{pval(g.p_better)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Угадано — в среднем за тираж на проверочной половине (поиск её не видел), у стратегии «лидер за всю историю».
            p &lt; 0,05 у одной игры из многих бывает и случайно.{' '}
            {Object.keys(st.skipped ?? {}).length > 0 && (
              <button className="link-btn" onClick={() => setShowSkipped((v) => !v)}>
                {showSkipped ? 'Скрыть' : 'Не вошли'} ({Object.keys(st.skipped).length})
              </button>
            )}
          </p>
          {showSkipped && (
            <ul className="plain small muted">
              {Object.entries(st.skipped).map(([s, why]) => <li key={s}>{why}</li>)}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
