import { NextResponse } from 'next/server'
import { latestJob, startJob, type JobKind } from '@/lib/jobs'
import { isValidSlug } from '@/lib/paths'

export const dynamic = 'force-dynamic'

const KINDS: JobKind[] = ['fetch', 'scan', 'analyze', 'godmode', 'auto', 'rules', 'chaos']
const NEEDS_GAME: JobKind[] = ['analyze', 'godmode', 'chaos']

function parse(kind: unknown, game: unknown): { kind: JobKind; game: string | null } | string {
  if (!KINDS.includes(kind as JobKind)) return 'Неизвестный тип задачи'
  if (game != null && game !== '' && !isValidSlug(game)) return 'Недопустимое имя игры'
  const g = game ? String(game) : null
  if (NEEDS_GAME.includes(kind as JobKind) && !g) return 'Не указана игра'
  return { kind: kind as JobKind, game: g }
}

export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams
  const p = parse(sp.get('kind'), sp.get('game'))
  if (typeof p === 'string') return NextResponse.json({ error: p }, { status: 400 })
  return NextResponse.json({ job: latestJob(p.kind, p.game) ?? null })
}

export async function POST(req: Request) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Ожидается JSON' }, { status: 400 })
  }
  const p = parse(body.kind, body.game)
  if (typeof p === 'string') return NextResponse.json({ error: p }, { status: 400 })
  const params: Record<string, unknown> = {}
  if (p.kind === 'godmode') {
    // без бюджета — до исчерпания перебора, не дольше 8 часов
    const budget = Number(body.budget ?? 480)
    if (!Number.isFinite(budget) || budget < 1 || budget > 480) {
      return NextResponse.json({ error: 'Бюджет — от 1 до 480 минут' }, { status: 400 })
    }
    params.budget = budget
    params.resume = body.resume === true
  }
  return NextResponse.json({ job: startJob(p.kind, p.game, params) })
}
