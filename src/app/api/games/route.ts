import { NextResponse } from 'next/server'
import { listGames, readScan } from '@/lib/games'
import { APP_VERSION } from '@/lib/version'

export const dynamic = 'force-dynamic'

export async function GET() {
  const scan = readScan()
  const verdicts = new Map((scan?.games ?? []).map((g) => [String(g.slug), g]))
  const games = listGames().map((g) => {
    const v = verdicts.get(g.slug)
    return {
      ...g,
      scan: v ? { level: v.level, verdict: v.verdict, q: v.q_value ?? null, draws: v.draws } : null,
    }
  })
  return NextResponse.json({ version: APP_VERSION, scanAt: scan?.generated_at ?? null, games })
}
