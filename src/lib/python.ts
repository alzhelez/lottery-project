import { spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { PROJECT_ROOT } from './paths'

/** Python-интерпретатор: PYTHON_BIN → .venv проекта → ~/.venv → системный. */
export function pythonBin(): string {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN
  const win = process.platform === 'win32'
  const rel = win ? path.join('Scripts', 'python.exe') : path.join('bin', 'python')
  for (const venv of [path.join(PROJECT_ROOT, '.venv'), path.join(os.homedir(), '.venv')]) {
    const p = path.join(venv, rel)
    if (fs.existsSync(p)) return p
  }
  return win ? 'python' : 'python3'
}

export const ENGINE = path.join(PROJECT_ROOT, 'python', 'lp.py')

/** Короткая синхронная команда движка: возвращает событие result или бросает ошибку. */
export function runEngine(args: string[], timeoutMs = 60_000): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin(), [ENGINE, ...args], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
      windowsHide: true,
    })
    let out = ''
    let err = ''
    const timer = setTimeout(() => child.kill(), timeoutMs)
    child.stdout.setEncoding('utf-8')
    child.stderr.setEncoding('utf-8')
    child.stdout.on('data', (c: string) => { out += c })
    child.stderr.on('data', (c: string) => { err = (err + c).slice(-4000) })
    child.on('error', (e) => { clearTimeout(timer); reject(new Error(`Не удалось запустить Python: ${e.message}`)) })
    child.on('close', () => {
      clearTimeout(timer)
      const events = out.split('\n').filter((l) => l.startsWith('@@')).map((l) => {
        try { return JSON.parse(l.slice(2)) } catch { return null }
      }).filter(Boolean) as Array<Record<string, unknown>>
      const error = events.find((e) => e.type === 'error')
      const result = events.reverse().find((e) => e.type === 'result')
      if (error) reject(new Error(String(error.message)))
      else if (result) resolve(result)
      else reject(new Error(err.trim().split('\n').slice(-1)[0] || 'движок не вернул результат'))
    })
  })
}
