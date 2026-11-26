'use client'

import { useCallback, useEffect, useState } from 'react'

interface GameChange {
    date: string
    reason: string
}

interface JobState {
    id: string
    status: 'running' | 'done' | 'error' | 'cancelled'
    error?: string | null
    result?: { reset?: Record<string, unknown> } | null
}

export function ResetPanel({ slug }: { slug: string }) {
    const [changes, setChanges] = useState<GameChange[]>([])
    const [date, setDate] = useState('')
    const [job, setJob] = useState<JobState | null>(null)
    const [error, setError] = useState('')

    const refreshJob = useCallback(async () => {
        const r = await fetch(`/api/jobs?kind=reset&game=${encodeURIComponent(slug)}`, {
            cache: 'no-store',
        })
        const payload = await r.json()
        setJob(payload.job ?? null)
    }, [slug])

    useEffect(() => {
        fetch(`/api/game-changes?game=${encodeURIComponent(slug)}`, { cache: 'no-store' })
            .then((r) => r.json())
            .then((payload) => {
                setChanges(payload.changes ?? [])
                if (payload.latest) setDate(payload.latest)
            })
            .catch(() => {})
        refreshJob()
    }, [slug, refreshJob])

    useEffect(() => {
        if (job?.status !== 'running') return
        const timer = window.setTimeout(refreshJob, 1500)
        return () => window.clearTimeout(timer)
    }, [job?.status, refreshJob])

    async function run(clear = false) {
        setError('')
        const r = await fetch('/api/jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                kind: 'reset',
                game: slug,
                ...(clear
                    ? { clear: true }
                    : { date }),
            }),
        })
        const payload = await r.json()
        if (!r.ok) {
            setError(payload.error ?? 'Не удалось запустить пересчёт')
            return
        }
        setJob(payload.job)
    }

    const latest = changes.at(-1)

    return (
        <section className="panel" data-testid="reset-panel">
            <h3>Точка отсчёта после изменения правил</h3>
            <p className="muted small">
                Архив не удаляется. Методы, доверие и история прогнозов будут пересчитаны только по тиражам
                начиная с выбранной даты.
            </p>

            {latest && (
                <p className="small">
                    Последнее изменение: <strong>{latest.date}</strong> — {latest.reason}
                </p>
            )}

            <div className="run-bar">
                <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    data-testid="reset-date"
                />
                <button
                    className="btn"
                    onClick={() => run(false)}
                    disabled={!date || job?.status === 'running'}
                    data-testid="run-reset"
                >
                    {job?.status === 'running' ? 'Идёт пересчёт…' : 'Считать от этой даты'}
                </button>
                <button
                    className="btn btn-ghost"
                    onClick={() => run(true)}
                    disabled={job?.status === 'running'}
                    data-testid="clear-reset"
                >
                    Считать весь архив
                </button>
            </div>

            {changes.length > 0 && (
                <details className="small">
                    <summary>Даты изменений ({changes.length})</summary>
                    <ul>
                        {changes.map((c) => (
                            <li key={c.date}>
                                <button className="link-btn" onClick={() => setDate(c.date)}>{c.date}</button>
                                {' '}— {c.reason}
                            </li>
                        ))}
                    </ul>
                </details>
            )}

            {job?.status === 'running' && <p className="muted">Сохраняю точку отсчёта и пересчитываю методы…</p>}
            {job?.status === 'done' && <p className="muted">Точка отсчёта применена, пересчёт завершён.</p>}
            {(error || job?.status === 'error') && (
                <p className="error">Ошибка: {error || job?.error}</p>
            )}
        </section>
    )
}