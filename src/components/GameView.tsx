'use client'
import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { AnalysisMethods, AnalysisOverview, type Analysis } from './AnalysisPanels'
import { ChaosPanel } from './ChaosPanel'
import { dateOnly, nf, plural, span } from './format'
import { GodModePanel } from './GodModePanel'
import { JournalPanel } from './JournalPanel'
import { OddsPanel } from './OddsPanel'
import { RulesPanel } from './RulesPanel'
import { MyTickets } from './MyTickets'
import { TicketsPanel } from './TicketsPanel'
import { useJob } from './useJob'

export interface Info {
  slug: string
  title: string
  stolotoUrl: string
  draws: number
  first: { no: number; date: string } | null
  last: { no: number; date: string } | null
  nextNo: number | null
  missing: number
  activity: { active: boolean; daysSinceLast: number | null; checkedAt: string | null; dataAgeDays: number | null; threshold: number }
}

const TABS = [
  { id: 'overview', label: 'Обзор' },
  { id: 'methods', label: 'Сравнение методов' },
  { id: 'chaos', label: 'Порядок из хаоса' },
  { id: 'god', label: 'Режим Бога' },
  { id: 'journal', label: 'Журнал прогнозов' },
  { id: 'odds', label: 'Шансы' },
  { id: 'tickets', label: 'Билеты' },
  { id: 'mine', label: 'Мои билеты' },
  { id: 'rules', label: 'Правила' },
] as const

const EXPORTS = [
  { format: 'xlsx', what: 'all', label: 'Всё в Excel (.xlsx)' },
  { format: 'csv', what: 'draws', label: 'Тиражи (.csv)' },
  { format: 'csv', what: 'journal', label: 'Журнал прогнозов (.csv)' },
  { format: 'csv', what: 'methods', label: 'Сравнение методов (.csv)' },
  { format: 'csv', what: 'godmode', label: 'Лента режима Бога (.csv)' },
]

export function GameView({ info }: { info: Info }) {
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('overview')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loaded, setLoaded] = useState(false)

  const loadAnalysis = useCallback(async () => {
    const r = await fetch(`/api/games/${info.slug}/results?kind=analysis`, { cache: 'no-store' })
    setAnalysis((await r.json()).result)
    setLoaded(true)
  }, [info.slug])
  useEffect(() => { loadAnalysis() }, [loadAnalysis])
  const job = useJob('analyze', info.slug, loadAnalysis)

  const stale = analysis && info.last && analysis.last_draw_no !== info.last.no

  return (
    <main className="page">
      <nav className="crumbs"><Link href="/">Все игры</Link></nav>
      <section className="game-head">
        <div>
          <h1 data-testid="game-title">{info.title}</h1>
          <a href={info.stolotoUrl} target="_blank" rel="noreferrer" className="ext" data-testid="stoloto-link">
            Страница игры на stoloto.ru
          </a>
        </div>
        <div className="head-actions">
          {info.nextNo != null && (info.activity.active ? (
            <div className="next-draw" data-testid="next-draw">
              <span className="next-label">Прогноз на тираж</span>
              <span className="next-no">№{info.nextNo}</span>
            </div>
          ) : (
            <div className="next-draw inactive" data-testid="next-draw">
              <span className="next-label">Следующего тиража нет</span>
              <span className="next-no">Игра не проводится</span>
            </div>
          ))}
          {info.draws > 0 && (
            <details className="export-menu">
              <summary className="btn btn-ghost" data-testid="export-menu">Экспорт</summary>
              <div className="menu">
                {EXPORTS.map((e) => (
                  <a key={e.label} href={`/api/games/${info.slug}/export?format=${e.format}&what=${e.what}`} download
                    data-testid={`export-${e.format}-${e.what}`}>{e.label}</a>
                ))}
              </div>
            </details>
          )}
        </div>
      </section>

      {info.draws === 0 ? (
        <p className="empty">Тиражи этой игры ещё не загружены. Загрузите их <Link href="/">на главной странице</Link>.</p>
      ) : (
        <>
          <dl className="facts">
            <div>
              <dt>Тиражей в архиве</dt>
              <dd data-testid="draw-count">{nf.format(info.draws)}</dd>
              {info.missing > 0 && <dd className="sub">пропущено {nf.format(info.missing)} {plural(info.missing, 'номер', 'номера', 'номеров')}</dd>}
            </div>
            <div>
              <dt>Период игры</dt>
              <dd data-testid="period">{dateOnly(info.first?.date)} — {dateOnly(info.last?.date)}</dd>
              <dd className="sub">{info.first && info.last ? span(info.first.date, info.last.date) : ''}</dd>
            </div>
            <div>
              <dt>Последний тираж</dt>
              <dd>№{info.last?.no}</dd>
              <dd className="sub">{info.last?.date}</dd>
            </div>
          </dl>

          {!info.activity.active && (
            <p className="banner" data-testid="inactive-banner">
              Тиражей не было {Math.floor(info.activity.daysSinceLast ?? 0)} {plural(Math.floor(info.activity.daysSinceLast ?? 0), 'день', 'дня', 'дней')}{' '}
              (порог — {info.activity.threshold}): игра считается устаревшей. Анализ истории доступен, но прогнозы
              в журнал не записываются.
              {!info.activity.checkedAt && ' Архив этой игры ещё не проверялся загрузчиком — возможно, данные просто не обновлены.'}
            </p>
          )}
          {info.activity.active && (info.activity.dataAgeDays ?? 0) > 1 && (
            <p className="banner">
              Архив проверялся {Math.floor(info.activity.dataAgeDays ?? 0)} {plural(Math.floor(info.activity.dataAgeDays ?? 0), 'день', 'дня', 'дней')} назад.
              Загрузите новые тиражи перед прогнозом: прогноз, сделанный после тиража, журнал не засчитает.
            </p>
          )}

          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? 'tab on' : 'tab'}
                onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}>{t.label}</button>
            ))}
          </div>

          {(tab === 'overview' || tab === 'methods' || tab === 'chaos') && (
            <div className="run-bar">
              <button className="btn" onClick={() => job.start()} disabled={job.running} data-testid="run-analysis">
                {job.running ? 'Идёт анализ…' : analysis ? 'Пересчитать анализ' : 'Запустить анализ'}
              </button>
              {job.running && (
                <span className="muted">
                  {job.job?.progress?.model ? `Проверяю: ${job.job.progress.model} (${job.job.progress.done} из ${job.job.progress.total})` : 'Тесты случайности…'}
                </span>
              )}
              {!job.running && analysis && (
                <span className="muted">Рассчитано {analysis.generated_at.replace('T', ' ')} по тиражам до №{analysis.last_draw_no}.</span>
              )}
              {stale && !job.running && <span className="warn">Появились новые тиражи — пересчитайте анализ.</span>}
              {job.job?.status === 'error' && <span className="error">Ошибка: {job.job.error}</span>}
              {job.error && <span className="error">{job.error}</span>}
            </div>
          )}

          {tab === 'overview' && (analysis ? <AnalysisOverview a={analysis} /> : loaded && <p className="empty">Запустите анализ — он займёт от секунд до пары минут.</p>)}
          {tab === 'methods' && (analysis ? <AnalysisMethods a={analysis} nextNo={info.nextNo} /> : loaded && <p className="empty">Запустите анализ, чтобы сравнить методы.</p>)}
          {tab === 'chaos' && <ChaosPanel slug={info.slug} chaos={analysis?.chaos} loaded={loaded} onDone={loadAnalysis} />}
          {tab === 'god' && <GodModePanel info={info} />}
          {tab === 'journal' && <JournalPanel info={info} />}
          {tab === 'odds' && <OddsPanel slug={info.slug} />}
          {tab === 'tickets' && <TicketsPanel slug={info.slug} />}
          {tab === 'mine' && <MyTickets slug={info.slug} />}
          {tab === 'rules' && <RulesPanel slug={info.slug} stolotoUrl={info.stolotoUrl} />}
        </>
      )}
    </main>
  )
}
