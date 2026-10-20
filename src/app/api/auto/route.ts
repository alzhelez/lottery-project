import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { latestJob } from '@/lib/jobs'
import { dataDir } from '@/lib/paths'

export const dynamic = 'force-dynamic'

/** Статус автозапуска: последний цикл (data/auto_status.json) и идёт ли он сейчас. */
export async function GET() {
  let status: Record<string, unknown> | null = null
  try {
    status = JSON.parse(fs.readFileSync(path.join(dataDir(), 'auto_status.json'), 'utf-8'))
  } catch {
    status = null
  }
  const running = latestJob('auto', null)?.status === 'running'
  // цикл из Планировщика Windows идёт в отдельном процессе: жив ли он — по auto.lock
  let external = false
  try {
    const lock = JSON.parse(fs.readFileSync(path.join(dataDir(), 'auto.lock'), 'utf-8'))
    process.kill(Number(lock.pid), 0)
    external = true
  } catch {
    external = false
  }
  if (status && status.status === 'running' && !running && !external) status = { ...status, status: 'interrupted' }
  return NextResponse.json({ status, running: running || external })
}
