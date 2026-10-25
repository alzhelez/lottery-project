'use client'
import { useCallback, useEffect, useState } from 'react'
import { useJob } from './useJob'

interface AutoStatus {
  started_at: string
  finished_at: string | null
  status: 'running' | 'done' | 'error' | 'interrupted'
  error?: string
  seconds?: number
  current?: { stage: string; game: string | null; since: string }
  games: Record<string, { analyzed?: boolean; added?: number; journal_checked?: number; skipped?: string }>
  backup?: { dir: string; count: number; last: { name: string; modified: string; bytes: number } | null }
}

const when = (s: string | null | undefined) => (s ? s.replace('T', ' ').slice(0, 16) : '—')
const size = (b: number) => (b < 1e6 ? `${Math.max(1, Math.round(b / 1e3))} КБ` : `${(b / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} МБ`)

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
  const [tg, setTg] = useState<{ configured: boolean; has_token: boolean; proxy?: boolean; queued?: number; queued_since?: string | null } | null>(null)
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
          {status.status === 'running' && (
            <> — идёт{status.current && <>: {status.current.stage}{status.current.game && ` (${status.current.game})`} с {status.current.since.slice(11, 16)}</>}.
              {status.current && Date.now() - new Date(status.current.since).getTime() > 30 * 60_000 &&
                <span className="warn"> Этап идёт больше 30 минут — возможно, цикл завис (например, после сна компьютера); следующий запуск через 3 часа остановит его сам.</span>}
            </>
          )}
          {status.status === 'done' && status.seconds != null && <span className="muted"> Цикл занял {Math.round(status.seconds / 60)} мин.</span>}
          {status.status === 'error' && <span className="error"> — ошибка: {status.error}</span>}
          {status.status === 'interrupted' && <span className="warn"> — прерван.</span>}
        </p>
      ) : (
        <p className="small muted">Ещё не запускался.</p>
      )}
      {status?.backup && (
        <p className="small" data-testid="backup-status">
          Резервная копия журнала и билетов:{' '}
          {status.backup.last
            ? <>последняя {when(status.backup.last.modified)} ({size(status.backup.last.bytes)}), всего {status.backup.count}</>
            : 'ещё не делалась'}
          <span className="sub">Раз в сутки, хранятся последние 30, папка <code>{status.backup.dir}</code>. Вернуть: <code>lp.bat backup restore имя-архива</code>.</span>
        </p>
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
        {tg?.queued ? (
          <span className="sub warn" data-testid="telegram-queue">
            Telegram недоступен: {tg.queued} сообщ. ждут отправки с {when(tg.queued_since)}.
            {!tg.proxy && ' Если так бывает часто, api.telegram.org блокируется провайдером — задайте TELEGRAM_PROXY в .env (docs/TELEGRAM.md).'}
          </span>
        ) : null}
      </p>
      <p className="small muted">
        Цикл: загрузка тиражей → сверка журнала → анализ активных игр с прогнозом на следующий тираж. Чтобы журнал
        пополнялся сам, запустите <code>schedule.bat</code> (Планировщик Windows, по умолчанию раз в час) или
        <code> docker compose up</code>.
      </p>
    </div>
  )
}
