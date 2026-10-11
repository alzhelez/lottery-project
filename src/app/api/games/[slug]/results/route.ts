import { NextResponse } from 'next/server'
import { readGameInfo, readJson, readResult } from '@/lib/games'
import { isValidSlug, resultsFile } from '@/lib/paths'

export const dynamic = 'force-dynamic'

export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const kind = new URL(req.url).searchParams.get('kind')
  if (!isValidSlug(slug) || (kind !== 'analysis' && kind !== 'godmode')) {
    return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  }
  const result = readResult(slug, kind)
  if (kind !== 'godmode') return NextResponse.json({ result })
  // можно ли продолжить: состояние сохранено по тем же тиражам, что сейчас в архиве
  const state = readJson<{ signature: { last_draw_no: number; draws: number }; elapsed: number; experts: number;
    exhausted: boolean; stages_done: string[] }>(resultsFile(slug, 'godmode_state.json'))
  const info = readGameInfo(slug)
  return NextResponse.json({
    result,
    state: state && {
      ...state,
      resumable: Boolean(info?.last && state.signature.last_draw_no === info.last.no),
    },
  })
}
