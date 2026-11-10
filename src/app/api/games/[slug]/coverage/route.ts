import { NextResponse } from 'next/server'
import { isValidSlug } from '@/lib/paths'
import { coverage } from '@/lib/predictions'

export const dynamic = 'force-dynamic'

/** Автоанализ игры: у всех ли тиражей периода есть сверенные предсказания каждого метода. */
export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  return NextResponse.json(coverage(slug))
}
