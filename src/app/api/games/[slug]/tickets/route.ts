import { NextResponse } from 'next/server'
import { isValidSlug } from '@/lib/paths'
import { runEngine } from '@/lib/python'

export const dynamic = 'force-dynamic'

/** {count} — сгенерировать билеты; {check: "1,2,3|4"} — разобрать свою комбинацию. */
export async function POST(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  if (!isValidSlug(slug)) return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  let body: { count?: unknown; check?: unknown }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Ожидается JSON' }, { status: 400 })
  }
  const args = ['tickets', '--game', slug]
  if (typeof body.check === 'string') {
    if (!/^[\d,\s|]{1,300}$/.test(body.check)) return NextResponse.json({ error: 'Числа через запятую, поля через |' }, { status: 400 })
    args.push('--check', body.check)
  } else {
    const count = Number(body.count ?? 5)
    if (!Number.isInteger(count) || count < 1 || count > 50) return NextResponse.json({ error: 'Билетов — от 1 до 50' }, { status: 400 })
    args.push('--count', String(count))
  }
  try {
    // служебное поле события движка наружу не отдаём: ответ — {tickets} или {check}
    const { type: _type, ...result } = await runEngine(args, 60_000)
    return NextResponse.json(result)
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 })
  }
}
