import { NextResponse } from 'next/server'
import { runEngine } from '@/lib/python'

export const dynamic = 'force-dynamic'

/** Настроены ли уведомления в Telegram (движок читает .env при каждом запуске). */
export async function GET() {
  try {
    const r = await runEngine(['telegram', 'status'], 30_000)
    return NextResponse.json(r.telegram)
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 })
  }
}

/** Отправить тестовое сообщение. */
export async function POST() {
  try {
    const r = await runEngine(['telegram', 'test'], 60_000)
    return NextResponse.json({ sent: r.sent })
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 400 })
  }
}
