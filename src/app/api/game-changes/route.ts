import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { PROJECT_ROOT } from '@/lib/paths'

export const dynamic = 'force-dynamic'

export async function GET(req: Request) {
    const slug = new URL(req.url).searchParams.get('game')
    if (!slug) return NextResponse.json({ error: 'Не указана игра' }, { status: 400 })

    const file = path.join(PROJECT_ROOT, 'config', 'game_changes.json')
    let payload: any = {}
    try {
        payload = JSON.parse(fs.readFileSync(file, 'utf-8'))
    } catch {
        return NextResponse.json({ changes: [], latest: null })
    }

    const changes = (payload.games?.[slug] ?? []).slice().sort((a: any, b: any) =>
        String(a.date).localeCompare(String(b.date))
    )

    return NextResponse.json({
        changes,
        latest: changes.length ? changes[changes.length - 1].date : null,
    })
}