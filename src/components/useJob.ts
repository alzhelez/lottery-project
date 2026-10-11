'use client'
import { useCallback, useEffect, useRef, useState } from 'react'

export interface Job {
  id: string
  kind: string
  game: string | null
  status: 'running' | 'done' | 'error' | 'cancelled'
  startedAt: number
  finishedAt: number | null
  params: Record<string, unknown>
  progress: Record<string, any> | null
  games: Record<string, Record<string, any>>
  gameOrder: string[]
  log: string[]
  error: string | null
  result: Record<string, any> | null
  next: string | null
  external?: boolean
}

/** Подписка на фоновую задачу: подхватывает уже идущую, опрашивает статус, пока она работает. */
export function useJob(kind: string, game: string | null, onFinish?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const finishRef = useRef(onFinish)
  finishRef.current = onFinish
  const lastStatus = useRef<string | null>(null)

  const apply = useCallback((j: Job | null) => {
    setJob(j)
    if (j && lastStatus.current === 'running' && j.status !== 'running') finishRef.current?.(j)
    lastStatus.current = j?.status ?? null
  }, [])

  /** Подхватить последнюю задачу этого типа (например, запущенную сервером автоматически). */
  const refresh = useCallback(async () => {
    const qs = new URLSearchParams({ kind, ...(game ? { game } : {}) })
    try {
      const d = await (await fetch(`/api/jobs?${qs}`)).json()
      if (d.job && d.job.status === 'running') lastStatus.current = 'running'
      apply(d.job)
    } catch {
      /* нет связи с сервером */
    }
  }, [kind, game, apply])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (!job || job.status !== 'running') return
    const timer = setInterval(async () => {
      try {
        const r = await fetch(`/api/jobs/${job.id}`)
        if (r.ok) apply((await r.json()).job)
      } catch {
        /* сервер перезапускается — попробуем на следующем шаге */
      }
    }, 1200)
    return () => clearInterval(timer)
  }, [job, apply])

  const start = useCallback(async (params: Record<string, unknown> = {}) => {
    setError(null)
    const r = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ kind, game, ...params }),
    })
    const d = await r.json()
    if (!r.ok) {
      setError(d.error ?? 'Не удалось запустить задачу')
      return null
    }
    lastStatus.current = 'running'
    setJob(d.job)
    return d.job as Job
  }, [kind, game])

  const cancel = useCallback(async () => {
    if (!job) return
    const r = await fetch(`/api/jobs/${job.id}`, { method: 'DELETE' })
    if (r.ok) apply((await r.json()).job)
  }, [job, apply])

  return { job, start, cancel, refresh, error, running: job?.status === 'running' }
}
