'use client'
import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { dateOnly, nf, plural, span } from './format'
import { AutoBox } from './AutoBox'
import { SetupModal } from './SetupModal'
import { useJob } from './useJob'

interface GameRow {
  slug: string
  title: string
  draws: number
  first: { no: number; date: string } | null
  last: { no: number; date: string } | null
  nextNo: number | null
  missing: number
  activity: { active: boolean; daysSinceLast: number | null; checkedAt: string | null; dataAgeDays: number | null; threshold: number }
  scan: { level: string; verdict: string; q: number | null } | null
}

const LEVEL: Record<string, string> = {
  random: 'Случайная',
  weak: 'Отклонения без пользы',
  signal: 'Есть отклонения',
  na: 'Не анализируется',
}

export function HomeView() {
  const [games, setGames] = useState<GameRow[] | null>(null)
  const [scanAt, setScanAt] = useState<string | null>(null)
  const [modal, setModal] = useState(false)
  const [showEmpty, setShowEmpty] = useState(false)
  const [showOld, setShowOld] = useState(false)

  const load = useCallback(async () => {
    const r = await fetch('/api/games', { cache: 'no-store' })
    const d = await r.json()
    setGames(d.games)
    setScanAt(d.scanAt)
    return d.games as GameRow[]
  }, [])

  useEffect(() => {
    load().then((g) => {
      if (!g.some((x) => x.draws > 0)) setModal(true)
    })
  }, [load])

  const scan = useJob('scan', null, () => load())

  const withData = (games ?? []).filter((g) => g.draws > 0).sort((a, b) => b.draws - a.draws)
  const active = withData.filter((g) => g.activity.active)
  const obsolete = withData.filter((g) => !g.activity.active)
    .sort((a, b) => (a.activity.daysSinceLast ?? 1e9) - (b.activity.daysSinceLast ?? 1e9))
  const threshold = games?.[0]?.activity.threshold ?? 15
  const neverChecked = withData.some((g) => !g.activity.checkedAt)
  const staleData = withData.some((g) => (g.activity.dataAgeDays ?? 0) > 1)
  const empty = (games ?? []).filter((g) => g.draws === 0)
  const total = withData.reduce((s, g) => s + g.draws, 0)
  const titles = Object.fromEntries((games ?? []).map((g) => [g.slug, g.title]))

  return (
    <main className="page">
      <section className="hero">
        <div>
          <h1>Тиражи Столото под микроскопом</h1>
          <p className="lead">
            {games === null ? 'Загружаю список игр…' : withData.length
              ? `${withData.length} ${plural(withData.length, 'игра', 'игры', 'игр')} с данными (активных: ${active.length}), ${nf.format(total)} ${plural(total, 'тираж', 'тиража', 'тиражей')} в архиве.`
              : 'Архив пуст. Загрузите тиражи, чтобы начать.'}
          </p>
        </div>
        <div className="hero-actions">
          <button className="btn" onClick={() => setModal(true)} data-testid="open-setup">Загрузить тиражи</button>
          <button className="btn btn-ghost" onClick={() => scan.start()} disabled={scan.running || !withData.length}
            data-testid="run-scan">
            {scan.running ? `Проверяю ${scan.job?.progress?.done ?? 0} из ${scan.job?.progress?.total ?? '…'}` : 'Проверить игры на случайность'}
          </button>
        </div>
      </section>

      <p className="note">
        Проверка ищет в истории тиражей закономерности, которые теоретически помогают прогнозу: неравные частоты,
        повторы чисел из прошлых тиражей, устойчивость «горячих» чисел, связи пар. Поправка на множество проверок
        не даёт случайным совпадениям выглядеть как открытие.
        {scanAt && <> Последняя проверка: {scanAt.replace('T', ' ')}.</>}
      </p>

      <AutoBox onDone={load} />

      {(neverChecked || staleData) && withData.length > 0 && (
        <p className="warn" data-testid="stale-warning">
          {neverChecked
            ? 'Архив части игр ещё не проверялся загрузчиком — актуальность игр определена по сегодняшней дате. Загрузите тиражи, чтобы обновить данные.'
            : 'Данные части игр не обновлялись больше суток — загрузите тиражи, чтобы список активных игр был точным.'}
        </p>
      )}

      <h2 className="section-title">Активные игры <span className="muted">({active.length})</span></h2>
      {active.length > 0 ? (
        <GamesTable rows={active} testId="games-table" />
      ) : (
        <p className="empty">Нет игр с тиражами за последние {threshold} дней.</p>
      )}

      {obsolete.length > 0 && (
        <>
          <h2 className="section-title">
            <button className="link-btn" onClick={() => setShowOld((v) => !v)} data-testid="toggle-obsolete" aria-expanded={showOld}>
              Устаревшие игры ({obsolete.length})
            </button>
          </h2>
          <p className="muted small">Тиражей не было больше {threshold} дней — игра не проводится или приостановлена.</p>
          {showOld && <GamesTable rows={obsolete} testId="obsolete-table" obsolete />}
        </>
      )}

      {empty.length > 0 && (
        <p>
          <button className="link-btn" onClick={() => setShowEmpty((v) => !v)}>
            {showEmpty ? 'Скрыть' : 'Показать'} игры без загруженных тиражей ({empty.length})
          </button>
        </p>
      )}
      {showEmpty && (
        <ul className="empty-games">
          {empty.map((g) => <li key={g.slug}><Link href={`/games/${g.slug}`}>{g.title}</Link></li>)}
        </ul>
      )}

      <SetupModal open={modal} onClose={() => setModal(false)} onChanged={load} titles={titles} />
    </main>
  )
}

function GamesTable({ rows, testId, obsolete = false }: { rows: GameRow[]; testId: string; obsolete?: boolean }) {
  return (
    <div className="table-wrap">
      <table className="games" data-testid={testId}>
        <thead>
          <tr>
            <th>Игра</th>
            <th className="r">Тиражей</th>
            <th>Период</th>
            <th className="r">{obsolete ? 'Без тиражей' : 'Следующий'}</th>
            <th>Проверка на случайность</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((g) => (
            <tr key={g.slug} data-testid={`row-${g.slug}`}>
              <td><Link href={`/games/${g.slug}`} className="game-link">{g.title}</Link></td>
              <td className="r num">{nf.format(g.draws)}</td>
              <td>{dateOnly(g.first?.date)} — {dateOnly(g.last?.date)}<span className="sub">{g.first && g.last ? span(g.first.date, g.last.date) : ''}</span></td>
              <td className="r num">
                {obsolete
                  ? `${Math.floor(g.activity.daysSinceLast ?? 0)} ${plural(Math.floor(g.activity.daysSinceLast ?? 0), 'день', 'дня', 'дней')}`
                  : `№${g.nextNo}`}
              </td>
              <td>
                {g.scan ? (
                  <span className={`verdict lv-${g.scan.level}`} title={g.scan.verdict}>{LEVEL[g.scan.level] ?? g.scan.level}</span>
                ) : <span className="muted">не проверялась</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
