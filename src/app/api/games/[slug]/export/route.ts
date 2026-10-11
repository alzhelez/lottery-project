import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { dataDir, isValidSlug } from '@/lib/paths'
import { runEngine } from '@/lib/python'

export const dynamic = 'force-dynamic'

const WHAT = ['all', 'draws', 'journal', 'methods', 'tests', 'godmode']

export async function GET(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const sp = new URL(req.url).searchParams
  const format = sp.get('format') ?? 'xlsx'
  const what = sp.get('what') ?? (format === 'xlsx' ? 'all' : 'draws')
  if (!isValidSlug(slug) || !['xlsx', 'csv'].includes(format) || !WHAT.includes(what)) {
    return NextResponse.json({ error: 'Неверный запрос' }, { status: 400 })
  }
  const name = format === 'xlsx' ? `${slug}.xlsx` : `${slug}_${what}.csv`
  const out = path.join(dataDir(), 'exports', name)
  try {
    await runEngine(['export', '--game', slug, '--format', format, '--what', what, '--out', out], 120_000)
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 404 })
  }
  const body = fs.readFileSync(out)
  return new NextResponse(body, {
    headers: {
      'content-type': format === 'xlsx'
        ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        : 'text/csv; charset=utf-8',
      'content-disposition': `attachment; filename="${name}"`,
      'cache-control': 'no-store',
    },
  })
}
