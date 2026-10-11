import { spawn, type ChildProcess } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { ENGINE, pythonBin } from './python'
import fs from 'node:fs'
import path from 'node:path'
import { dataDir, PROJECT_ROOT, resultsFile } from './paths'

export type JobKind = 'fetch' | 'scan' | 'analyze' | 'godmode' | 'auto'
export type JobStatus = 'running' | 'done' | 'error' | 'cancelled'

export interface Job {
  id: string
  kind: JobKind
  game: string | null
  status: JobStatus
  startedAt: number
  finishedAt: number | null
  params: Record<string, unknown>
  progress: Record<string, unknown> | null
  games: Record<string, Record<string, unknown>>
  gameOrder: string[]
  log: string[]
  error: string | null
  result: Record<string, unknown> | null
  next: string | null
  external?: boolean   // процесс запущен вне приложения (консоль, Планировщик) или до перезапуска сервера
}

interface Registry {
  jobs: Map<string, Job>
  procs: Map<string, ChildProcess>
}

// переживает перезагрузку модулей в dev-режиме
const g = globalThis as unknown as { __lotteryJobs?: Registry }
const reg: Registry = g.__lotteryJobs ?? (g.__lotteryJobs = { jobs: new Map(), procs: new Map() })

const MAX_LOG = 60

function push(job: Job, line: string) {
  job.log.push(line)
  if (job.log.length > MAX_LOG) job.log.splice(0, job.log.length - MAX_LOG)
}

export function publicJob(job: Job) {
  return job
}

export function findJob(id: string): Job | undefined {
  const ext = parseExternalId(id)
  if (ext) {
    // внешний процесс закончился — отдаём «завершено», чтобы интерфейс перечитал результат
    return externalJob(ext.kind, ext.game) ?? {
      id, kind: ext.kind, game: ext.game, status: 'done', startedAt: 0, finishedAt: Date.now(), params: {},
      progress: null, games: {}, gameOrder: [], log: [], error: null, result: null, next: null, external: true,
    }
  }
  return reg.jobs.get(id)
}

export function latestJob(kind: JobKind, game: string | null): Job | undefined {
  let found: Job | undefined
  for (const job of reg.jobs.values()) {
    if (job.kind === kind && job.game === game && (!found || job.startedAt > found.startedAt)) found = job
  }
  if (found?.status === 'running') return found
  return externalJob(kind, game) ?? found
}

// ── Процессы, запущенные вне приложения ─────────────────────────────────────
// Режим Бога и автозапуск пишут lock-файл с PID (и файл прогресса), поэтому их видно,
// даже если они запущены из консоли, Планировщиком или до перезапуска сервера.

function lockFile(kind: JobKind, game: string | null): string | null {
  if (kind === 'godmode' && game) return resultsFile(game, 'godmode.lock')
  if (kind === 'auto') return path.join(dataDir(), 'auto.lock')
  return null
}

function readJsonFile(file: string): Record<string, any> | null {
  try { return JSON.parse(fs.readFileSync(file, 'utf-8')) } catch { return null }
}

export function pidAlive(pid: number): boolean {
  if (!Number.isInteger(pid) || pid <= 0) return false
  try {
    process.kill(pid, 0)   // сигнал 0 только проверяет существование процесса (в т.ч. на Windows)
    return true
  } catch (e) {
    return (e as NodeJS.ErrnoException).code === 'EPERM'
  }
}

export function externalJob(kind: JobKind, game: string | null): Job | undefined {
  const file = lockFile(kind, game)
  if (!file) return undefined
  const lock = readJsonFile(file)
  if (!lock || !pidAlive(Number(lock.pid))) return undefined
  // PID мог достаться другому процессу: lock режима Бога старше бюджета + часа — устарел
  const started = Date.parse(lock.started_at)
  if (kind === 'godmode' && started && Date.now() - started > (Number(lock.budget) || 480) * 60_000 + 3_600_000) return undefined
  if ([...reg.procs.values()].some((p) => p.pid === Number(lock.pid))) return undefined
  const progress = kind === 'godmode' && game ? readJsonFile(resultsFile(game, 'godmode.progress.json')) : null
  return {
    id: `ext:${kind}:${game ?? ''}`, kind, game, status: 'running',
    startedAt: Date.parse(lock.started_at) || Date.now(), finishedAt: null,
    params: { budget: lock.budget }, progress, games: {}, gameOrder: [], log: [], error: null,
    result: null, next: null, external: true,
  }
}

function parseExternalId(id: string): { kind: JobKind; game: string | null } | null {
  const m = /^ext:(godmode|auto):([a-z0-9_-]*)$/.exec(id)
  return m ? { kind: m[1] as JobKind, game: m[2] || null } : null
}

function argsFor(kind: JobKind, game: string | null, params: Record<string, unknown>): string[] {
  switch (kind) {
    case 'fetch':
      return ['fetch', ...(game ? ['--game', game] : [])]
    case 'scan':
      return ['scan']
    case 'analyze':
      return ['analyze', '--game', game!]
    case 'godmode':
      return ['godmode', '--game', game!, '--budget', String(params.budget ?? 30), ...(params.resume ? ['--resume'] : [])]
    case 'auto':
      return ['auto']
  }
}

function handleEvent(job: Job, ev: Record<string, unknown>) {
  switch (ev.type) {
    case 'progress':
    case 'checkpoint':
      job.progress = { ...(job.progress ?? {}), ...ev }
      break
    case 'games':
      job.gameOrder = (ev.games as string[]) ?? []
      for (const s of job.gameOrder) job.games[s] = { status: 'queued' }
      break
    case 'game': {
      const slug = String(ev.game)
      job.games[slug] = { ...(job.games[slug] ?? {}), ...ev }
      if (!job.gameOrder.includes(slug)) job.gameOrder.push(slug)
      break
    }
    case 'log':
      push(job, String(ev.message ?? ''))
      break
    case 'result':
      job.result = ev
      break
    case 'error':
      job.error = String(ev.message ?? 'Неизвестная ошибка')
      break
  }
}

/** Запускает задачу или возвращает уже идущую такую же (та же команда и игра). */
export function startJob(kind: JobKind, game: string | null, params: Record<string, unknown> = {}): Job {
  const running = latestJob(kind, game)
  if (running && running.status === 'running') return running
  // одновременно может идти только один процесс, который пишет состояние режима Бога
  if (kind === 'godmode' && game && externalJob(kind, game)) return externalJob(kind, game)!

  const job: Job = {
    id: randomUUID(), kind, game, status: 'running', startedAt: Date.now(), finishedAt: null,
    params, progress: null, games: {}, gameOrder: [], log: [], error: null, result: null, next: null,
  }
  reg.jobs.set(job.id, job)

  const child = spawn(pythonBin(), [ENGINE, ...argsFor(kind, game, params)], {
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
    windowsHide: true,
  })
  reg.procs.set(job.id, child)

  let buf = ''
  child.stdout.setEncoding('utf-8')
  child.stdout.on('data', (chunk: string) => {
    buf += chunk
    let nl: number
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim()
      buf = buf.slice(nl + 1)
      if (line.startsWith('@@')) {
        try {
          handleEvent(job, JSON.parse(line.slice(2)))
        } catch {
          push(job, line)
        }
      } else if (line) push(job, line)
    }
  })
  let errTail = ''
  child.stderr.setEncoding('utf-8')
  child.stderr.on('data', (chunk: string) => {
    errTail = (errTail + chunk).slice(-4000)
  })
  child.on('error', (err) => {
    job.status = 'error'
    job.error = `Не удалось запустить Python (${pythonBin()}): ${err.message}. Укажите путь в PYTHON_BIN.`
    job.finishedAt = Date.now()
  })
  child.on('close', (code) => {
    reg.procs.delete(job.id)
    job.finishedAt = Date.now()
    if (job.status === 'cancelled') return
    if (code === 0 && !job.error) {
      job.status = 'done'
      // после загрузки тиражей сразу проверяем все игры на случайность
      if (kind === 'fetch') job.next = startJob('scan', null).id
    } else {
      job.status = 'error'
      if (!job.error) {
        const lastLine = errTail.trim().split('\n').slice(-1)[0]
        job.error = lastLine || `Процесс завершился с кодом ${code}`
      }
      if (errTail) push(job, errTail.trim().split('\n').slice(-8).join('\n'))
    }
  })
  return job
}

export function cancelJob(id: string): Job | undefined {
  const ext = parseExternalId(id)
  if (ext) {
    const job = externalJob(ext.kind, ext.game)
    const lock = readJsonFile(lockFile(ext.kind, ext.game)!)
    if (job && lock) {
      try { process.kill(Number(lock.pid)) } catch { /* уже завершён */ }
      return { ...job, status: 'cancelled', finishedAt: Date.now() }
    }
    return job
  }
  const job = reg.jobs.get(id)
  if (!job || job.status !== 'running') return job
  job.status = 'cancelled'
  job.finishedAt = Date.now()
  reg.procs.get(id)?.kill()
  return job
}
