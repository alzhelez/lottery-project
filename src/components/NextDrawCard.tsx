'use client'
import { useCallback, useEffect, useState } from 'react'
import { BlockBalls } from './Balls'
import { nf, num, pval } from './format'
import { useJob } from './useJob'

interface Rec {
  checked: number; mean_hits?: number; expected?: number; p_sequential?: number | null; goal?: string
  excess_pct?: number; mde_pct?: number | null; need?: number | null; proven?: boolean
}
interface Rarity { score: number; flags: string[] }
interface Source {
  source: string; title: string; detail: string; numbers: number[][]; made_at: string | null; record: Rec | null
  rarity?: Rarity | null
}
interface NextData {
  draw_no: number | null; date?: string | null; how?: string | null; last_no?: number; active: boolean; draws?: number
  analysis_at?: string | null; super_prize?: number | null
  sources: Source[]
  common?: number[][]
  archive?: Source[]
  v2?: Source[]
  archive_titles?: string[]
  rare?: { numbers: number[][]; notes: string[] } | null
  money?: { return: number; usual_return: number | null; price: number | null
    peak: { days: number; max: number | null; is_max: boolean } | null } | null
  least: { numbers: number[][] | null; model: string; consensus: number[][] | null; conclusion: string | null; record: Rec | null } | null
}

const SHORT: Record<string, string> = { analysis_best: 'Л', analysis_consensus: 'К', chaos: 'Х', godmode: 'Б', experiment: 'Э', golden: 'З', final: 'Ф',
  final_v2: 'Ф2', consensus_v2: 'К2', godmode_v2: 'Б2', least_v2: 'Н2' }

function left(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const two = (v: number) => String(v).padStart(2, '0')
  return d ? `${d} д ${two(h)}:${two(m)}:${two(sec)}` : `${two(h)}:${two(m)}:${two(sec)}`
}

/** Честная рамка: насколько результат метода отличим от случайности и сколько прогнозов для этого нужно. */
export function HonestFrame({ r, fewer }: { r: { checked?: number; n?: number; mde_pct?: number | null; need?: number | null; proven?: boolean }; fewer?: boolean }) {
  const n = r.checked ?? r.n ?? 0
  if (!n || r.mde_pct == null) return null
  const side = fewer ? 'реже' : 'лучше'
  return (
    <span className="sub" data-testid="honest-frame">
      {r.proven
        ? <>отрыв уже отличим от случайности (обычный порог, без поправки на число методов и игр)</>
        : r.need != null
          ? <>чтобы отличить такой отрыв от случайности, нужно ≈ {nf.format(r.need)} прогнозов — сейчас {nf.format(n)}{r.need > n * 20 ? ': пока это шум' : ''}</>
          : <>отрыва в сторону «{side} случайного» нет; на {nf.format(n)} прогнозах заметен был бы отрыв от ±{num(r.mde_pct, r.mde_pct < 10 ? 1 : 0)}%</>}
    </span>
  )
}

function RecordLine({ r, fewer }: { r: Rec | null; fewer?: boolean }) {
  if (!r || !r.checked) return <span className="sub">по журналу: ещё нет сверенных прогнозов</span>
  const proven = r.p_sequential != null && r.p_sequential < 0.05
  return (
    <>
      <span className="sub">
        по журналу: {nf.format(r.checked)} сверено, {fewer ? 'выпало' : 'угадано'} в среднем {num(r.mean_hits, 2)} при {num(r.expected, 2)} у случайного выбора
        {r.p_sequential != null && <>, последовательное p {pval(r.p_sequential)}</>}
        {' — '}{proven ? <b className="hit-text">{fewer ? 'устойчиво реже случайного' : 'устойчиво лучше случайного'}</b> : fewer ? 'пока не реже случайных чисел' : 'пока не лучше случайного выбора'}
      </span>
      <HonestFrame r={r} fewer={fewer} />
    </>
  )
}

/** Пометка популярности комбинации: шанс выигрыша она не меняет, только то, со сколькими придётся делить приз. */
function RarityTag({ r }: { r?: Rarity | null }) {
  if (!r) return null
  return r.score > 0 ? (
    <span className="sub" data-testid="rarity-popular">
      <span className="status-tag st-error">популярная комбинация</span>{' '}
      {r.flags.join('; ')}. В категориях, где приз делится, его придётся делить с большим числом людей.
    </span>
  ) : (
    <span className="sub" data-testid="rarity-rare"><span className="status-tag st-done">редкая комбинация</span> признаков популярного выбора нет</span>
  )
}

function SourceRow({ s, common, size, fewer }: { s: Source; common?: number[][]; size: 'lg' | 'md' | 'sm'; fewer?: boolean }) {
  return (
    <div className="next-source" data-testid={`next-${s.source}`}>
      <span className="src-chip" title={s.title}>{SHORT[s.source]}</span>
      <div>
        <div className="src-title">{s.title}{s.detail && <span className="muted">: {s.detail}</span>}</div>
        <BlockBalls blocks={s.numbers} marked={common} size={size} tone={fewer ? 'cold' : undefined} />
        <RarityTag r={s.rarity} />
        <RecordLine r={s.record} fewer={fewer} />
      </div>
    </div>
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
  // архивные методы посчитаны кнопкой в автоанализе — перечитать карточку
  useEffect(() => {
    window.addEventListener('lottery:forecast', load)
    return () => window.removeEventListener('lottery:forecast', load)
  }, [load])
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
        <p className="muted">
          {!data.active ? 'Игра устарела: тиражей давно не было, прогнозы не пишутся.'
            : (data.draws ?? 0) < 300 ? `В архиве ${nf.format(data.draws ?? 0)} тиражей — для прогноза нужно хотя бы 300.`
              : 'Прогноза на ближайший тираж нет: тиражи загружены после последнего анализа или анализ ещё не запускался.'}
        </p>
        {data.active && (data.draws ?? 0) >= 300 && <div className="run-bar">{refresh}</div>}
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
          {data.money && (
            <p className="muted small" data-testid="next-money">
              Ожидаемый возврат: <b>{num(data.money.return, 2)}</b> на рубль ставки
              {data.money.usual_return != null && <> (обычно {num(data.money.usual_return, 2)})</>}
              {data.money.peak?.is_max
                ? <> — <span className="status-tag st-done" data-testid="next-money-peak">максимум за {data.money.peak.days} дн. наблюдений</span></>
                : data.money.peak?.max != null && data.money.peak.days >= 14
                  ? <>; максимум за {Math.min(data.money.peak.days, 180)} дн. наблюдений — {num(data.money.peak.max, 2)}</> : null}
              . {data.money.return >= 1 ? 'Больше рубля — редкий случай; почти все билеты всё равно проигрывают.' : 'Меньше рубля: в среднем ставка возвращается не полностью.'}
            </p>
          )}
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
              <SourceRow key={s.source} s={s} common={data.common} size={s.source === 'final' ? 'lg' : 'md'} />
            ))}
          </div>
          {data.sources.filter((s) => s.source !== 'final').length >= 2 && (
            <p className="muted small" data-testid="next-common">
              {data.common?.some((b) => b.length) ? (
                <>
                  <span className="ball ball-predict ball-common" style={{ width: '1.1rem', height: '1.1rem', marginRight: 8, verticalAlign: 'middle' }} aria-hidden />
                  Обводкой отмечены числа, которые есть в прогнозе каждого метода ({data.sources.map((s) => SHORT[s.source]).join(', ')}):{' '}
                  <b>{data.common.map((b) => b.join(' ') || '—').join(' | ')}</b>. «Наименее вероятные» в сравнении не участвуют.
                </>
              ) : <>Чисел, которые есть в прогнозе каждого метода ({data.sources.map((s) => SHORT[s.source]).join(', ')}), на этот тираж нет.</>}
            </p>
          )}
          {data.rare && (
            <div className="next-source" data-testid="next-rare">
              <span className="src-chip" title="Редкая комбинация">Р</span>
              <div>
                <div className="src-title">Редкая комбинация<span className="muted">: не прогноз — числа, которые редко ставят</span></div>
                <BlockBalls blocks={data.rare.numbers} tone="plain" size="md" />
                <span className="sub">
                  {data.rare.notes.join('; ')}. Шанс выигрыша такой же, как у любой другой комбинации; смысл есть только там, где
                  приз делится между победителями (суперприз): делить его придётся с меньшим числом людей. В журнал не пишется.
                </span>
              </div>
            </div>
          )}
          {!!data.archive?.length && (
            <details className="next-archive" data-testid="next-archive" style={{ margin: '.6rem 0' }}>
              <summary style={{ cursor: 'pointer' }}><b>Архив</b> <span className="muted small">— методы, запущенные вручную: {data.archive.map((s) => s.title).join(', ')}</span></summary>
              <div className="next-sources">
                {data.archive.map((s) => <SourceRow key={s.source} s={s} size="sm" />)}
              </div>
              <p className="muted small">Архивные методы в «Финальном предсказании» и в подсветке общих чисел не участвуют; их прогноз записан в журнал и будет сверен.</p>
            </details>
          )}
          {!!data.v2?.length && (
            <div className="next-v2" data-testid="next-v2" style={{ margin: '.8rem 0' }}>
              <h3>Версия 2</h3>
              <p className="muted small">
                Те же методы, но голос модели весит по её результату на последних тиражах (полураспад 150 тиражей), а не по
                всей истории: если розыгрыш изменился, v2 перестраивается быстрее. Считается рядом с первой версией; кто из
                них точнее на одних и тех же тиражах — в «Статистике», блок «Версия 2 против первой».
              </p>
              <div className="next-sources">
                {data.v2.map((s) => <SourceRow key={s.source} s={s} size="md" fewer={s.source === 'least_v2'} />)}
              </div>
            </div>
          )}
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
