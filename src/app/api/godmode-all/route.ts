import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { pidAlive } from '@/lib/jobs'
import { dataDir, resultsFile } from '@/lib/paths'

export const dynamic = 'force-dynamic'

function readJson(file: string): Record<string, any> | null {
  try { return JSON.parse(fs.readFileSync(file, 'utf-8')) } catch { return null }
}

/** Всеобъемлющий режим Бога: состояние прохода (data/results/godmode_all.json) и идёт ли он. */
export async function GET() {
  const state = readJson(resultsFile(null, 'godmode_all.json'))
  const lock = readJson(path.join(dataDir(), 'godmode_all.lock'))
  const running = !!lock && pidAlive(Number(lock.pid))
  // процесс остановлен (кнопкой, перезагрузкой, сном компьютера) — проход можно продолжить
  if (state && state.status === 'running' && !running) state.status = 'stopped'
  return NextResponse.json({ state, running })
}
