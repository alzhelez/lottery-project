import { NextResponse } from 'next/server'
import { isValidSlug } from '@/lib/paths'
import { runEngine } from '@/lib/python'

export const dynamic = 'force-dynamic'

const ID = /^[0-9a-f]{12}$/

async function engine(args: string[]) {
  try {
    // служебное поле события движка наружу не отдаём
    const { type: _type, ...result } = await runEngine(args, 60_000)
    return NextResponse.json(result)
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 400 })
  }
}

async function body(req: Request): Promise<Record<string, unknown> | null> {
  try {
    const b = await req.json()
    return b && typeof b === 'object' ? b as Record<string, unknown> : null
  } catch {
    return null
  }
}

function bad(error: string) {
  return NextResponse.json({ error }, { status: 400 })
}

/** Мои билеты: все игры или одна (?game=…): билеты, итог, для формы — ближайший тираж и цена. */
export async function GET(req: Request) {
  const game = new URL(req.url).searchParams.get('game')
  if (game !== null && !isValidSlug(game)) return bad('Неверный запрос')
  return engine(['mytickets', 'list', ...(game ? ['--game', game] : [])])
}

/** Внести билет: {game, numbers: "1,2,3|4", draws?, draw_no?, price?, note?}. */
export async function POST(req: Request) {
  const b = await body(req)
  if (!b) return bad('Ожидается JSON')
  const { game, numbers, draws, draw_no: drawNo, price, note } = b
  if (typeof game !== 'string' || !isValidSlug(game)) return bad('Выберите игру')
  if (typeof numbers !== 'string' || !/^[\d,;\s|]{1,300}$/.test(numbers) || !/\d/.test(numbers)) return bad('Числа через запятую, поля через «|»')
  const args = ['mytickets', 'add', '--game', game, '--numbers', numbers]
  if (draws != null) {
    if (!Number.isInteger(draws) || (draws as number) < 1 || (draws as number) > 100) return bad('Тиражей — от 1 до 100')
    args.push('--draws', String(draws))
  }
  if (drawNo != null) {
    if (!Number.isInteger(drawNo) || (drawNo as number) < 1) return bad('Неверный номер тиража')
    args.push('--draw', String(drawNo))
  }
  if (price != null) {
    if (typeof price !== 'number' || !Number.isFinite(price) || price < 0 || price > 1_000_000) return bad('Цена — от 0 до 1 000 000 ₽')
    args.push('--price', String(price))
  }
  if (note != null) {
    if (typeof note !== 'string' || note.length > 200) return bad('Заметка — до 200 символов')
    if (note.trim()) args.push('--note', note.trim())
  }
  return engine(args)
}

/** Выигрыш вручную: {game, id, won: число ₽ или null — вернуть расчёт по таблице призов}. */
export async function PATCH(req: Request) {
  const b = await body(req)
  if (!b) return bad('Ожидается JSON')
  const { game, id, won } = b
  if (typeof game !== 'string' || !isValidSlug(game) || typeof id !== 'string' || !ID.test(id)) return bad('Неверный запрос')
  if (won !== null && (typeof won !== 'number' || !Number.isFinite(won) || won < 0 || won > 1e10)) return bad('Выигрыш — число от 0 ₽')
  return engine(['mytickets', 'won', '--game', game, '--id', id, `--won=${won === null ? -1 : won}`])
}

/** Удалить билет: ?game=…&id=… */
export async function DELETE(req: Request) {
  const q = new URL(req.url).searchParams
  const game = q.get('game') ?? ''
  const id = q.get('id') ?? ''
  if (!isValidSlug(game) || !ID.test(id)) return bad('Неверный запрос')
  return engine(['mytickets', 'remove', '--game', game, '--id', id])
}
