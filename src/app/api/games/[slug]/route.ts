import { NextResponse } from 'next/server'
import { readGameInfo } from '@/lib/games'

export const dynamic = 'force-dynamic'

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const info = readGameInfo(slug)
  if (!info) return NextResponse.json({ error: 'Игра не найдена' }, { status: 404 })
  return NextResponse.json(info)
}
