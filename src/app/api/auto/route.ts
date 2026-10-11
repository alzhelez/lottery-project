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
  if (status && status.status === 'running' && !running) status = { ...status, status: 'interrupted' }
  return NextResponse.json({ status, running })
}
