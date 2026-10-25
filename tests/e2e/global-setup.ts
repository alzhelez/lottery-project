import fs from 'node:fs'
import path from 'node:path'

export default function globalSetup() {
  const dir = path.join(__dirname, '.data')
  fs.rmSync(dir, { recursive: true, force: true })
  // резервные копии журнала автозапуск кладёт рядом с папкой данных
  fs.rmSync(path.join(__dirname, 'backup'), { recursive: true, force: true })
  fs.mkdirSync(path.join(dir, 'draws'), { recursive: true })
}
