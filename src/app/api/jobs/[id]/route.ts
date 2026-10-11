import { NextResponse } from 'next/server'
import { cancelJob, findJob } from '@/lib/jobs'

export const dynamic = 'force-dynamic'

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const job = findJob((await params).id)
  if (!job) return NextResponse.json({ error: 'Задача не найдена' }, { status: 404 })
  return NextResponse.json({ job })
}

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const job = cancelJob((await params).id)
  if (!job) return NextResponse.json({ error: 'Задача не найдена' }, { status: 404 })
  return NextResponse.json({ job })
}
