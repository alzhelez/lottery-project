import path from 'node:path'
import { NextResponse } from 'next/server'
import { readJson } from '@/lib/games'
import { dataDir, isValidSlug } from '@/lib/paths'

export const dynamic = 'force-dynamic'

/** Правила игры со stoloto.ru (data/rules/<игра>.json, пишет `lp.py rules` и загрузка тиражей). */
export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  const rules = readJson(path.join(dataDir(), 'rules', `${slug}.json`))
  const nextdraw = readJson<{ games: Record<string, unknown> }>(path.join(dataDir(), 'results', 'nextdraw.json'))
  return NextResponse.json({ rules, nextDraw: nextdraw?.games?.[slug] ?? null })
}
