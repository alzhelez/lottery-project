import { NextResponse } from 'next/server'
import { gameTitle } from '@/lib/games'
import { isValidSlug } from '@/lib/paths'
import { digitalExport } from '@/lib/predictions'

export const dynamic = 'force-dynamic'

const DAYS = [0, 1, 3, 7, 14, 30]      // 0 — все тиражи

/** Выгрузка прогнозов «в цифровом виде»: текстовый файл, строка на метод (ФП, ЛМА, КМ, …). */
export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const days = Number(new URL(req.url).searchParams.get('days') ?? 7)
  if (!isValidSlug(slug) || !DAYS.includes(days)) {
    return NextResponse.json({ error: 'Период — 1, 3, 7, 14, 30 дней или 0 (все тиражи)' }, { status: 400 })
  }
  const name = `prognozy_${slug}_${days > 0 ? `${days}d` : 'all'}.txt`
  return new NextResponse(digitalExport(slug, gameTitle(slug), days), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Disposition': `attachment; filename="${name}"` },
  })
}
