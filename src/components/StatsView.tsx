'use client'
import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { nf, num, pval } from './format'
import { useJob } from './useJob'

interface Row {
  source: string; title: string; goal?: 'fewer'; checked: number; half: number
  share: number | null; expected: number; expected_share: number | null; p_better: number | null
  mean_hits: number; mean_expected: number; excess_pct: number; p_mean: number | null
}
interface Game {
  slug: string; title: string; metric: 'half' | 'mean'; threshold: string | null; rows: Row[]
  best: Row | null; worst: Row | null; tie: boolean
  heterogeneity: { q: number; df: number; p: number; differ: boolean } | null
}
interface Watch {
  slug: string; title: string; source: string; source_title: string; goal?: 'fewer'
  checked: number; excess_pct: number; p: number; p_holm: number; halves: [number | null, number | null]; holds: boolean
}
interface TrustRow {
  source: string; title: string; n: number; hits: number; expected: number; excess_pct: number
  trust: number; level: string; few: boolean; rank: number
}
interface Trust { made_at?: string; days?: number; since?: string; games: Array<{ slug: string; title: string; rows: TrustRow[] }> }
interface Stats {
  games: Game[]; watch: Watch[]; trust: Trust | null
  retro: { status: { status: string; started_at: string; finished_at: string | null; days: number; since: string } | null
    games: Game[]; watch: Watch[] }
}

const MIN_RELIABLE = 30
const PERIODS: Array<[number, string]> = [[1, 'сутки'], [3, '3 дня'], [7, 'неделю'], [14, '2 недели'], [30, 'месяц']]
const LOWER = 'least'

function trustClass(t: number): string {
  return t >= 65 ? 'st-done' : t < 35 ? 'st-error' : ''
}

/** Рейтинг доверия: шкала 0–100 по каждому методу игры за период анализа (журнал + анализ за период). */
function TrustTable({ trust }: { trust: Trust }) {
  return (
    <div className="table-wrap">
      <table className="data compact" data-testid="trust-table">
        <thead>
          <tr>
            <th>Игра</th><th className="r">Место</th><th>Метод</th><th className="r">Доверие</th><th>Шкала</th>
            <th className="r">Прогнозов</th><th className="r">Угадано</th><th className="r">Случайный выбор</th><th className="r">Разница</th>
          </tr>
        </thead>
        <tbody>
          {trust.games.flatMap((g) => g.rows.map((r, i) => (
            <tr key={g.slug + r.source} data-testid="trust-row">
              <td style={{ whiteSpace: 'nowrap' }}>{i === 0 ? <Link href={`/games/${g.slug}`}>{g.title}</Link> : ''}</td>
              <td className="r num">{r.rank}</td>
              <td>{r.title}{r.source === LOWER && <span className="sub">чем меньше выпало его чисел, тем выше доверие</span>}</td>
              <td className="r num"><b>{num(r.trust, 0)}</b></td>
              <td>
                <span className={`status-tag ${r.few ? '' : trustClass(r.trust)}`}>{r.level}</span>
                {r.few && <span className="sub">меньше 30 прогнозов — оценка прижата к 50</span>}
              </td>
              <td className="r num">{nf.format(r.n)}</td>
              <td className="r num">{nf.format(r.hits)}</td>
              <td className="r num">{num(r.expected, 1)}</td>
              <td className="r num">{signed(r.excess_pct)}</td>
            </tr>
          )))}
        </tbody>
      </table>
    </div>
  )
}
const when = (s?: string | null) => (s ? s.replace('T', ' ').slice(0, 16) : '')

function share(v: number | null | undefined): string {
  return v == null ? '—' : `${num(v * 100, 1)}%`
}

function signed(v: number | null | undefined, digits = 1): string {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${num(v, digits)}%`
}

function method(r: Row | null, g: Game) {
  if (!r) return <span className="muted">—</span>
  return (
    <>
      {r.title}
      <span className="sub">
        {g.metric === 'half'
          ? <>{nf.format(r.half)} из {nf.format(r.checked)} ({share(r.share)})</>
          : <>{signed(r.excess_pct)} к случайному, {nf.format(r.checked)} прогнозов</>}
        {r.checked < MIN_RELIABLE ? ' · мало прогнозов' : ''}
      </span>
      {g.tie && <span className="sub">у всех методов одинаково</span>}
    </>
  )
}

function verdict(g: Game) {
  const h = g.heterogeneity
  if (!h) return <span className="muted">мало данных<span className="sub">нужно от {MIN_RELIABLE} прогнозов у двух методов</span></span>
  return h.differ
    ? <span data-testid="stats-differ">методы различаются<span className="sub">p = {pval(h.p)}</span></span>
    : <span data-testid="stats-random">разница случайна<span className="sub">p = {pval(h.p)} — «лучший» и «худший» здесь условны</span></span>
}

function GameTables({ games, testid }: { games: Game[]; testid: string }) {
  return (
    <>
      <div className="table-wrap">
        <table className="data" data-testid={`${testid}-summary`}>
          <thead>
            <tr><th>Игра</th><th>Что считаем</th><th>Лучший метод</th><th>Худший метод</th><th>Разница между методами</th></tr>
          </thead>
          <tbody>
            {games.map((g) => (
              <tr key={g.slug} data-testid={`${testid}-game`}>
                <td><Link href={`/games/${g.slug}`}>{g.title}</Link></td>
                <td className="num">{g.metric === 'half' ? g.threshold ?? '—' : 'среднее угаданных'}</td>
                <td data-testid={`${testid}-best`}>{method(g.best, g)}</td>
                <td data-testid={`${testid}-worst`}>{method(g.worst, g)}</td>
                <td>{verdict(g)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>По методам</h3>
      <div className="table-wrap">
        <table className="data compact" data-testid={`${testid}-methods`}>
          <thead>
            <tr>
              <th>Игра</th><th>Метод</th><th className="r">Сверено</th><th className="r">Угадал ≥ половины</th>
              <th className="r">Доля</th><th className="r">Случайный выбор</th><th className="r">Угадано в среднем</th>
              <th className="r">p</th>
            </tr>
          </thead>
          <tbody>
            {games.flatMap((g) => g.rows.map((r, i) => {
              const mark = g.tie ? '' : r.source === g.best?.source ? 'лучший' : r.source === g.worst?.source ? 'худший' : ''
              const p = g.metric === 'half' ? r.p_better : r.p_mean
              return (
                <tr key={g.slug + r.source} data-testid={`${testid}-row`} className={r.goal ? 'muted' : ''}>
                  <td style={{ whiteSpace: 'nowrap' }}>{i === 0 ? <Link href={`/games/${g.slug}`}>{g.title}</Link> : ''}</td>
                  <td>
                    {r.title}
                    {mark && <span className={`status-tag ${mark === 'лучший' ? 'st-done' : 'st-error'}`} style={{ marginLeft: 8 }}>{mark}</span>}
                    {r.goal && <span className="sub">цель — выпасть реже, в лучшие и худшие не входит</span>}
                  </td>
                  <td className="r num">{nf.format(r.checked)}</td>
                  {g.metric === 'half' ? (
                    <>
                      <td className="r num">{nf.format(r.half)}</td>
                      <td className="r num">{share(r.share)}</td>
                      <td className="r num">{num(r.expected, r.expected < 10 ? 2 : 1)}<span className="sub">{share(r.expected_share)}</span></td>
                    </>
                  ) : (
                    <>
                      <td className="r num muted" colSpan={2}>не считаем — см. примечание</td>
                      <td className="r num">{num(r.mean_expected, 2)}</td>
                    </>
                  )}
                  <td className="r num">{num(r.mean_hits, 2)}<span className="sub">{signed(r.excess_pct)}</span></td>
                  <td className="r num" style={{ whiteSpace: 'nowrap' }}>{p == null ? <span className="muted">мало данных</span> : pval(p)}</td>
                </tr>
              )
            }))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function WatchTable({ items, testid }: { items: Watch[]; testid: string }) {
  if (!items.length) {
    return <p className="empty" data-testid={`${testid}-empty`}>Пар с перевесом над случайным выбором (p &lt; 0,05) пока нет.</p>
  }
  return (
    <div className="table-wrap">
      <table className="data compact" data-testid={testid}>
        <thead>
          <tr>
            <th>Игра</th><th>Метод</th><th className="r">Прогнозов</th><th className="r">Перевес</th><th className="r">p</th>
            <th className="r">p с поправкой</th><th className="r">1-я половина</th><th className="r">2-я половина</th><th>Держится?</th>
          </tr>
        </thead>
        <tbody>
          {items.map((w) => (
            <tr key={w.slug + w.source} data-testid={`${testid}-row`}>
              <td><Link href={`/games/${w.slug}`}>{w.title}</Link></td>
              <td>{w.source_title}{w.goal && <span className="sub">выпадают реже — это и есть цель</span>}</td>
              <td className="r num">{nf.format(w.checked)}</td>
              <td className="r num">{signed(w.excess_pct)}</td>
              <td className="r num">{pval(w.p)}</td>
              <td className="r num">{pval(w.p_holm)}</td>
              <td className="r num">{signed(w.halves[0])}</td>
              <td className="r num">{signed(w.halves[1])}</td>
              <td>{w.holds ? <span className="status-tag st-done">в обеих половинах</span> : <span className="muted">только в одной</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Статистика: сколько раз каждый метод угадал не меньше половины чисел, лучший и худший метод игры,
 * пары «Под наблюдением» и ретро-проверка за неделю. slug — вкладка на странице игры. */
export function StatsView({ slug }: { slug?: string } = {}) {
  const [all, setAll] = useState<Stats | null>(null)
  const load = useCallback(() => {
    fetch('/api/stats', { cache: 'no-store' }).then((r) => r.json()).then(setAll).catch(() => {})
  }, [])
  const job = useJob('retro', null, () => load())
  const [days, setDays] = useState(7)
  useEffect(() => { load() }, [load])
  const Wrap = slug ? 'section' : 'main'
  const only = <T extends { slug: string }>(xs: T[]) => (slug ? xs.filter((g) => g.slug === slug) : xs)
  if (!all) return <Wrap className={slug ? '' : 'page'}><p className="muted">Загрузка…</p></Wrap>
  const games = only(all.games)
  const watch = only(all.watch)
  const retro = only(all.retro.games)
  const st = all.retro.status
  const trust = all.trust && { ...all.trust, games: only(all.trust.games) }
  const period = PERIODS.find(([d]) => d === days)?.[1] ?? `${days} дн.`

  return (
    <Wrap className={slug ? '' : 'page'} data-testid={slug ? 'stats-tab' : 'stats'}>
      {!slug && <h1>Статистика</h1>}
      <p className="note">
        По журналу прогнозов — только тем, что записаны до тиража и сверены после него. Для каждой игры и метода —
        сколько раз прогноз угадал <b>половину своих чисел или больше</b> (в «6 из 45» — от 3 из 6, в «4 из 20» — от 4 из
        8, считая все поля). Рядом — сколько таких раз в среднем дал бы случайный выбор того же числа чисел: метод
        полезен, только если заметно его обгоняет. Лучший и худший — по доле таких прогнозов; столбец «Разница между
        методами» говорит, отличаются ли методы игры больше, чем бывает случайно.
        {slug && <> Все игры сразу — в разделе <Link href="/stats">Статистика</Link> боковой панели.</>}
      </p>

      <h2>Доверие к методам</h2>
      <p className="note">
        Шкала 0–100 для каждого метода в каждой игре: 50 — как случайный выбор, выше — угадывал больше (у «наименее
        вероятных» наоборот: чем меньше выпало их чисел, тем выше), ниже — хуже случайного. Считается по анализу за
        выбранный период (все методы на каждом тираже периода) и настоящим прогнозам журнала за то же время. По этому
        рейтингу строится <b>«Финальное предсказание»</b> (Ф): голосование всех методов с весами по доверию. Доверие —
        не шанс выиграть: оно показывает, кому в этот период везло больше.
      </p>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <select className="input" value={days} onChange={(e) => setDays(Number(e.target.value))} disabled={job.running}
          data-testid="trust-period" aria-label="Период анализа">
          {PERIODS.map(([d, label]) => <option key={d} value={d}>за {label}</option>)}
        </select>
        <button type="button" className="btn" data-testid="retro-run" disabled={job.running}
          onClick={() => job.start({ days })}>
          {job.running ? 'Анализирую…' : `Провести анализ за ${period}`}
        </button>
        <span className="muted small" data-testid="retro-status">
          {job.running ? (job.job?.log?.slice(-1)[0] ?? 'идёт анализ: все методы на каждом тираже периода, режим Бога по 3 минуты на игру')
            : st?.status === 'done' ? `посчитано ${when(st.finished_at)} за ${st.days} дн., тиражи с ${when(st.since)}`
              : st?.status === 'running' ? `идёт с ${when(st.started_at)}` : 'ещё не проводился'}
        </span>
        {job.error && <span className="error">{job.error}</span>}
      </div>
      {trust && trust.games.length > 0
        ? <TrustTable trust={trust} />
        : <p className="empty" data-testid="trust-empty">Рейтинга пока нет — проведите анализ за период.</p>}

      <h2>Журнал прогнозов</h2>
      {games.length === 0 ? (
        <p className="empty">Сверенных прогнозов {slug ? 'по этой игре ' : ''}пока нет — они появятся после анализа и следующего тиража.</p>
      ) : (
        <>
          <GameTables games={games} testid="stats" />
          <p className="muted small">
            p — шанс, что случайный выбор угадал бы так же часто или чаще; считается от{' '}
            {MIN_RELIABLE} сверенных прогнозов. Среди многих игр и методов p &lt; 0,05 у одного-двух бывает просто случайно.
            Если случайный выбор угадывает половину своих чисел реже чем в 1% прогнозов (так в «Топ-3»: по цифре на
            каждую из 12 позиций), этот столбец почти всегда 0 — у таких игр «Что считаем» — среднее угаданных, и лучший
            и худший — по нему.
          </p>

          <h2>Под наблюдением</h2>
          <p className="note">
            Пары «игра — метод», где среднее угаданных лучше случайного выбора с p &lt; 0,05 (у «наименее вероятных» —
            выпадают реже), от {MIN_RELIABLE} прогнозов. «Держится» — перевес есть и в первой, и во второй половине
            прогнозов по времени. Только «p с поправкой» (Холма, на все проверенные пары) отвечает, не удача ли это:
            пока она не ниже 0,05, перевес может быть случайным.
          </p>
          <WatchTable items={watch} testid="stats-watch" />
        </>
      )}

      <h2>Анализ за период: все методы на каждом тираже</h2>
      <p className="note">
        Журнал успевает записать прогноз не на каждый тираж. Анализ за период восстанавливает, что дал бы каждый метод на
        <b> каждый</b> тираж выбранного периода, — только по тиражам до него; лучший метод выбран на отрезке истории,
        который закончился раньше этой недели. Это не то же самое, что прогноз, записанный заранее (так считает текущая
        версия программы), поэтому он показан отдельно от журнала. Запускается кнопкой «Провести анализ за …» выше;
        автозапуск повторяет его раз в неделю за тот же период.
      </p>
      {retro.length > 0 && (
        <>
          <GameTables games={retro} testid="retro" />
          <h3>Ретро: пары с перевесом</h3>
          <WatchTable items={only(all.retro.watch)} testid="retro-watch" />
        </>
      )}
    </Wrap>
  )
}
