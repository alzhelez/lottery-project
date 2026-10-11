'use client'
import { useEffect, useRef } from 'react'
import { nf } from './format'
import { useJob } from './useJob'

const STATUS: Record<string, string> = {
  queued: 'В очереди',
  running: 'Загрузка',
  done: 'Готово',
  no_data: 'Нет архива',
  error: 'Ошибка',
}

export function SetupModal({ open, onClose, onChanged, titles }: {
  open: boolean
  onClose: () => void
  onChanged: () => void
  titles: Record<string, string>
}) {
  const scanJob = useJob('scan', null, onChanged)
  const fetchJob = useJob('fetch', null, () => {
    onChanged()
    scanJob.refresh()   // сервер сам запускает проверку на случайность после загрузки
  })
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const d = dialog.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  const job = fetchJob.job
  const order = job?.gameOrder ?? []
  const finished = order.filter((s) => ['done', 'no_data', 'error'].includes(job?.games[s]?.status)).length
  const totalDraws = order.reduce((sum, s) => sum + (Number(job?.games[s]?.draws) || 0), 0)
  const scanning = scanJob.running
  const scanProg = scanJob.job?.progress
  const pct = order.length ? Math.round((finished / order.length) * 100) : 0

  return (
    <dialog ref={dialog} className="modal" onClose={onClose} aria-labelledby="setup-title">
      <header className="modal-head">
        <h2 id="setup-title">Загрузка тиражей</h2>
        <button className="icon-btn" onClick={onClose} aria-label="Закрыть окно">×</button>
      </header>
      <p className="muted">
        Скачиваем архивы всех игр со stoloto.ru. Уже загруженные игры только докачиваются новыми тиражами
        и пропусками. После загрузки все игры проверяются на случайность. Окно можно закрыть — загрузка
        продолжится в фоне.
      </p>

      <div className="modal-actions">
        {fetchJob.running ? (
          <button className="btn btn-ghost" onClick={fetchJob.cancel}>Остановить загрузку</button>
        ) : (
          <button className="btn" onClick={() => fetchJob.start()} disabled={scanning} data-testid="start-fetch">
            {job ? 'Загрузить заново' : 'Начать загрузку'}
          </button>
        )}
        {job && (
          <span className="muted" data-testid="fetch-summary">
            Игр: {finished} из {order.length || '…'}, тиражей: {nf.format(totalDraws)}
          </span>
        )}
      </div>
      {fetchJob.error && <p className="error">{fetchJob.error}</p>}

      {job && (
        <>
          <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${pct}%` }} />
          </div>
          {job.status === 'error' && <p className="error">Загрузка прервана: {job.error}</p>}
          {job.status === 'cancelled' && <p className="muted">Загрузка остановлена. Скачанные тиражи сохранены.</p>}
          <ul className="fetch-list">
            {order.map((slug) => {
              const g = job.games[slug] ?? {}
              return (
                <li key={slug} className={`fetch-row st-${g.status}`} data-testid={`fetch-${slug}`}>
                  <span className="fetch-name">{titles[slug] ?? slug}</span>
                  <span className="fetch-status">{STATUS[g.status] ?? g.status}</span>
                  <span className="fetch-draws">{g.draws ? nf.format(g.draws) : ''}</span>
                  <span className="fetch-msg">
                    {g.status === 'done' ? (g.added ? `+${nf.format(g.added)}` : 'без изменений') : (g.message ?? '')}
                    {g.journal_checked ? `, сверено прогнозов: ${g.journal_checked}` : ''}
                  </span>
                </li>
              )
            })}
          </ul>
        </>
      )}

      {(scanning || scanJob.job) && (
        <p className="scan-line" data-testid="scan-status">
          {scanning
            ? `Проверка игр на случайность: ${scanProg?.done ?? 0} из ${scanProg?.total ?? '…'}`
            : scanJob.job?.status === 'done'
              ? 'Проверка игр на случайность завершена — результаты в таблице.'
              : scanJob.job?.status === 'error' ? `Проверка не удалась: ${scanJob.job.error}` : ''}
        </p>
      )}
    </dialog>
  )
}
