import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { dataDir, isValidSlug } from '@/lib/paths'
import { runEngine } from '@/lib/python'

export const dynamic = 'force-dynamic'

type Params = { params: Promise<{ slug: string }> }

async function odds(slug: string) {
  const r = await runEngine(['odds', '--game', slug])
  return (r.odds as Record<string, unknown>)[slug] ?? null
}

export async function GET(_req: Request, { params }: Params) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  try {
    return NextResponse.json({ odds: await odds(slug) })
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 })
  }
}

/** Цена билета и суммы призов, которые ввёл пользователь (data/prizes/<игра>.json). */
export async function PUT(req: Request, { params }: Params) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  let body: { price?: unknown; prizes?: unknown }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Ожидается JSON' }, { status: 400 })
  }
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) && v > 0 && v < 1e12 ? v : null)
  const prizes: Record<string, number> = {}
  if (body.prizes && typeof body.prizes === 'object') {
    for (const [k, v] of Object.entries(body.prizes as Record<string, unknown>)) {
      if (/^\d+(\+\d+)*$/.test(k) && num(v) != null) prizes[k] = num(v)!
    }
  }
  const file = path.join(dataDir(), 'prizes', `${slug}.json`)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, JSON.stringify({ price: num(body.price), prizes }, null, 1), 'utf-8')
  try {
    return NextResponse.json({ odds: await odds(slug) })
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 })
  }
}
