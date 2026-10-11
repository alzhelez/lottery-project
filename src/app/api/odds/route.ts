import { NextResponse } from 'next/server'
import { runEngine } from '@/lib/python'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const r = await runEngine(['odds'], 120_000)
    return NextResponse.json({ odds: r.odds })
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 })
  }
}
