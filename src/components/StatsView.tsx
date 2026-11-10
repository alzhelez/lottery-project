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
interface TrustGame { slug: string; title: string; rows: TrustRow[] }
interface Stats {
  games: Game[]; watch: Watch[]
  trust: { made_at?: string; days?: number; since?: string; games: TrustGame[] } | null
  period: { days?: number; since?: string; games: Game[] } | null
  retro: { status: { status: string; started_at: string; finished_at: string | null; days: number; since: string } | null }
}

const MIN_RELIABLE = 30
const PERIODS: Array<[number, string]> = [[1, 'сутки'], [3, '3 дня'], [7, 'неделю'], [14, '2 недели'], [30, 'месяц']]
const LOWER = 'least'
const when = (s?: string | null) => (s ? s.replace('T', ' ').slice(0, 16) : '')

function share(v: number | null | undefined): string {
  return v == null ? '—' : `${num(v * 100, 1)}%`
}

function signed(v: number | null | undefined, digits = 1): string {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${num(v, digits)}%`
}

function trustClass(t: number): string {
  return t >= 65 ? 'st-done' : t < 35 ? 'st-error' : ''
}

function verdict(g: Game | undefined) {
  const h = g?.heterogeneity
  if (!h) return <span className="muted">мало данных<span className="sub">нужно от {MIN_RELIABLE} прогнозов у двух методов</span></span>
  return h.differ
    ? <span data-testid="stats-differ">методы различаются<span className="sub">p = {pval(h.p)}</span></span>
    : <span data-testid="stats-random">разница случайна<span className="sub">p = {pval(h.p)} — «лучший» и «худший» условны</span></span>
}

/** Рейтинг доверия одной игры: шкала 0–100 по каждому методу за период анализа. */
function TrustTable({ rows }: { rows: TrustRow[] }) {
  return (
    <div className="table-wrap">
      <table className="data compact" data-testid="trust-table">
        <thead>
          <tr>
            <th className="r">Место</th><th>Метод</th><th className="r">Доверие</th><th>Шкала</th>
            <th className="r">Прогнозов</th><th className="r">Угадано</th><th className="r">Случайный выбор</th><th className="r">Разница</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.source} data-testid="trust-row">
              <td className="r num">{r.rank}</td>
              <td>{r.title}{r.source === LOWER && <span className="sub">чем меньше выпало его чисел, тем выше доверие</span>}</td>
              <td className="r num"><b>{num(r.trust, 0)}</b></td>
              <td>
                <span className={`status-tag ${r.few ? '' : trustClass(r.trust)}`}>{r.level}</span>
                {r.few && <span className="sub">меньше {MIN_RELIABLE} прогнозов — оценка прижата к 50</span>}
              </td>
              <td className="r num">{nf.format(r.n)}</td>
              <td className="r num">{nf.format(r.hits)}</td>
              <td className="r num">{num(r.expected, 1)}</td>
              <td className="r num">{signed(r.excess_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** «По методам» одной игры: половина чисел и больше, среднее угаданных, p. */
function MethodsTable({ g, testid }: { g: Game; testid: string }) {
  return (
    <div className="table-wrap">
      <table className="data compact" data-testid={`${testid}-methods`}>
        <thead>
          <tr>
            <th>Метод</th><th className="r">Сверено</th><th className="r">Угадал ≥ половины</th>
            <th className="r">Доля</th><th className="r">Случайный выбор</th><th className="r">Угадано в среднем</th>
            <th className="r">p</th>
          </tr>
        </thead>
        <tbody>
          {g.rows.map((r) => {
            const mark = g.tie ? '' : r.source === g.best?.source ? 'лучший' : r.source === g.worst?.source ? 'худший' : ''
            const p = g.metric === 'half' ? r.p_better : r.p_mean
            return (
              <tr key={r.source} data-testid={`${testid}-row`} className={r.goal ? 'muted' : ''}>
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
          })}
        </tbody>
      </table>
    </div>
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

/** Статистика: доверие к методам и «По методам» за период анализа, журнал за всё время — по игре в
 * раскрывающемся блоке; «Под наблюдением». slug — вкладка на странице игры (блок сразу раскрыт). */
export function StatsView({ slug }: { slug?: string } = {}) {
  const [all, setAll] = useState<Stats | null>(null)
  const load = useCallback(() => {
    fetch('/api/stats', { cache: 'no-store' }).then((r) => r.json()).then(setAll).catch(() => {})
  }, [])
  const job = useJob('retro', null, () => load())
  const [days, setDays] = useState(7)
  useEffect(() => { load() }, [load])
  const Wrap = slug ? 'section' : 'main'
  if (!all) return <Wrap className={slug ? '' : 'page'}><p className="muted">Загрузка…</p></Wrap>
  const st = all.retro.status
  const period = PERIODS.find(([d]) => d === days)?.[1] ?? `${days} дн.`
  const trustBy = new Map((all.trust?.games ?? []).map((g) => [g.slug, g]))
  const periodBy = new Map((all.period?.games ?? []).map((g) => [g.slug, g]))
  const journalBy = new Map(all.games.map((g) => [g.slug, g]))
  const titles = new Map<string, string>()
  for (const g of [...all.games, ...(all.period?.games ?? []), ...(all.trust?.games ?? [])]) titles.set(g.slug, g.title)
  // сверху — игры, где у метода самое высокое доверие (оценки по малому числу прогнозов — ниже)
  const topTrust = (s: string) => {
    const r = trustBy.get(s)?.rows[0]
    return r ? (r.few ? 0 : 1000) + r.trust : -1
  }
  const slugs = [...titles.keys()].filter((s) => !slug || s === slug)
    .sort((a, b) => topTrust(b) - topTrust(a) || titles.get(a)!.localeCompare(titles.get(b)!, 'ru'))
  const watch = slug ? all.watch.filter((w) => w.slug === slug) : all.watch
  const analysed = all.period?.days ? `за ${all.period.days} дн. (с ${when(all.period.since)})` : ''

  return (
    <Wrap className={slug ? '' : 'page'} data-testid={slug ? 'stats-tab' : 'stats'}>
      {!slug && <h1>Статистика</h1>}
      <p className="note">
        <b>Доверие</b> — шкала 0–100 для каждого метода игры: 50 — как случайный выбор, выше — угадывал больше (у
        «наименее вероятных» наоборот). <b>По методам</b> — сколько раз прогноз угадал половину своих чисел или больше и
        сколько таких раз дал бы случайный выбор. Оба раздела считаются за период анализа: все методы на каждом тираже
        периода (только по тиражам до него) плюс настоящие прогнозы журнала за то же время. По доверию строится
        «Финальное предсказание». Доверие — не шанс выиграть: оно показывает, кому в этот период везло больше.
        {slug && <> Все игры — в разделе <Link href="/stats">Статистика</Link> боковой панели.</>}
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
      <p className="muted small">
        Кнопка пересчитывает «Доверие к методам» и «По методам» всех игр; автозапуск повторяет анализ раз в неделю за тот
        же период и обновляет доверие в каждом цикле.
      </p>

      {slugs.length === 0 && (
        <p className="empty" data-testid="trust-empty">Данных пока нет — проведите анализ за период или дождитесь первых сверенных прогнозов.</p>
      )}
      {slugs.length > 0 && !all.trust?.games.length && (
        <p className="empty" data-testid="trust-empty">Рейтинга доверия пока нет — проведите анализ за период.</p>
      )}

      {slugs.map((s) => {
        const t = trustBy.get(s)
        const p = periodBy.get(s)
        const j = journalBy.get(s)
        const top = t?.rows[0]
        return (
          <details key={s} className="card" {...(slug ? { open: true } : {})} data-testid="stats-game" style={{ marginTop: 12 }}>
            <summary style={{ cursor: 'pointer' }}>
              <b style={{ marginRight: 12 }}>{titles.get(s)}</b>
              {top
                ? <span className="muted small" data-testid="stats-top">выше всех доверие: {top.title} — {num(top.trust, 0)}{top.few ? ' (мало данных)' : ''}</span>
                : <span className="muted small">анализ за период не проводился</span>}
              {p && <span className="muted small" style={{ marginLeft: 12 }}>{p.heterogeneity ? (p.heterogeneity.differ ? 'методы различаются' : 'разница между методами случайна') : ''}</span>}
            </summary>

            <h3>Доверие к методам {analysed}</h3>
            {t ? <TrustTable rows={t.rows} /> : <p className="empty">Нет данных — проведите анализ за период.</p>}

            <h3>По методам {analysed}</h3>
            {p ? (
              <>
                <p className="muted small">
                  Считаем: {p.metric === 'half' ? `половина и больше — ${p.threshold ?? '—'}` : 'среднее угаданных'}. Разница между
                  методами: {verdict(p)}
                </p>
                <MethodsTable g={p} testid="stats" />
              </>
            ) : <p className="empty">Нет данных — проведите анализ за период.</p>}

            {j && (
              <>
                <h3>Журнал прогнозов за всё время</h3>
                <p className="muted small">Только прогнозы, записанные до тиража. Разница между методами: {verdict(j)}</p>
                <MethodsTable g={j} testid="journal" />
              </>
            )}
            {!slug && <p className="small"><Link href={`/games/${s}`}>Открыть игру →</Link></p>}
          </details>
        )
      })}

      <p className="muted small">
        p — шанс, что случайный выбор угадал бы так же часто или чаще; считается от {MIN_RELIABLE} сверенных прогнозов.
        Если случайный выбор угадывает половину своих чисел реже чем в 1% прогнозов (так в «Топ-3»: по цифре на каждую
        из 12 позиций), вместо этого сравнивается среднее угаданных. Анализ за период — не то же самое, что прогноз,
        записанный заранее: так считает текущая версия программы, поэтому журнал за всё время показан отдельно.
      </p>

      <details style={{ marginTop: 16 }} data-testid="stats-watch-block">
        <summary style={{ cursor: 'pointer' }}><b>Под наблюдением</b> <span className="muted small">— пары с перевесом над случайным в журнале: {watch.length}</span></summary>
        <p className="note">
          Пары «игра — метод», где среднее угаданных лучше случайного выбора с p &lt; 0,05 (у «наименее вероятных» —
          выпадают реже), от {MIN_RELIABLE} прогнозов журнала. «Держится» — перевес есть и в первой, и во второй половине
          прогнозов по времени. Только «p с поправкой» (Холма, на все проверенные пары) отвечает, не удача ли это.
        </p>
        <WatchTable items={watch} testid="stats-watch" />
      </details>
    </Wrap>
  )
}
