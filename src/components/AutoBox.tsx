'use client'
import { useCallback, useEffect, useState } from 'react'
import { useJob } from './useJob'

interface AutoStatus {
  started_at: string
  finished_at: string | null
  status: 'running' | 'done' | 'error' | 'interrupted'
  error?: string
  games: Record<string, { analyzed?: boolean; added?: number; journal_checked?: number; skipped?: string }>
}

const when = (s: string | null | undefined) => (s ? s.replace('T', ' ').slice(0, 16) : '—')

/** Автозапуск: последний цикл «загрузка → анализ → прогноз в журнал» и запуск вручную. */
export function AutoBox({ onDone }: { onDone: () => void }) {
  const [status, setStatus] = useState<AutoStatus | null>(null)
  const [running, setRunning] = useState(false)
  const load = useCallback(async () => {
    const d = await (await fetch('/api/auto', { cache: 'no-store' })).json()
    setStatus(d.status)
    setRunning(d.running)
  }, [])
  useEffect(() => { load() }, [load])
  const job = useJob('auto', null, () => { load(); onDone() })
  const [tg, setTg] = useState<{ configured: boolean; has_token: boolean } | null>(null)
  const [tgNote, setTgNote] = useState<string | null>(null)
  useEffect(() => {
    fetch('/api/telegram', { cache: 'no-store' }).then((r) => r.json()).then((d) => setTg(d.error ? null : d)).catch(() => {})
  }, [])
  async function testTelegram() {
    setTgNote('Отправляю…')
    const r = await fetch('/api/telegram', { method: 'POST' })
    const d = await r.json()
    setTgNote(r.ok ? 'Тестовое сообщение отправлено.' : d.error)
  }

  const games = status ? Object.values(status.games) : []
  const analyzed = games.filter((g) => g.analyzed).length
  const checked = games.reduce((s, g) => s + (g.journal_checked ?? 0), 0)
  const busy = job.running || running

  return (
    <div className="auto-box" data-testid="auto-box">
      <div className="run-bar" style={{ margin: 0 }}>
        <strong>Автозапуск</strong>
        <button className="btn btn-ghost" onClick={() => job.start()} disabled={busy} data-testid="run-auto">
          {busy ? 'Идёт цикл…' : 'Запустить цикл сейчас'}
        </button>
      </div>
      {status ? (
        <p className="small" data-testid="auto-status">
          Последний цикл: {when(status.started_at)}
          {status.status === 'done' && <> — готово: прогнозы по {analyzed} {analyzed === 1 ? 'игре' : 'играм'}, сверено прогнозов: {checked}.</>}
          {status.status === 'running' && ' — идёт.'}
          {status.status === 'error' && <span className="error"> — ошибка: {status.error}</span>}
          {status.status === 'interrupted' && <span className="warn"> — прерван.</span>}
        </p>
      ) : (
        <p className="small muted">Ещё не запускался.</p>
      )}
      <p className="small" data-testid="telegram-status">
        Уведомления в Telegram:{' '}
        {tg == null ? '…' : tg.configured ? (
          <>включены. <button className="link-btn" onClick={testTelegram} data-testid="telegram-test">Отправить тест</button></>
        ) : tg.has_token ? (
          <>нужен id чата — выполните <code>lp.bat telegram setup</code>.</>
        ) : (
          <>не настроены (как включить — в README, раздел «Уведомления в Telegram»).</>
        )}
        {tgNote && <span className="sub">{tgNote}</span>}
      </p>
      <p className="small muted">
        Цикл: загрузка тиражей → сверка журнала → анализ активных игр с прогнозом на следующий тираж. Чтобы журнал
        пополнялся сам, запустите <code>schedule.bat</code> (Планировщик Windows, по умолчанию раз в час) или
        <code> docker compose up</code>.
      </p>
    </div>
  )
}
