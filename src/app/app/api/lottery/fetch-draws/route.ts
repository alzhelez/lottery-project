import { NextResponse } from 'next/server'
import { join } from 'path'
import { tmpdir } from 'os'
import { validateGameId } from '@/lib/api-utils'
import { runPythonScript } from '@/lib/python-runner'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { game } = body

    const gameErr = validateGameId(game)
    if (gameErr) {
      return NextResponse.json({ error: gameErr }, { status: 400 })
    }

    if (!game) {
      return NextResponse.json(
        { error: 'Missing "game" parameter in request body' },
        { status: 400 }
      )
    }

    const outputFile = join(tmpdir(), `draws_${game}.txt`)

    const { stdout, stderr, code } = await runPythonScript('fetch.py', ['--game', game], {
      timeout: 600000,
    })

    try {
      const data = JSON.parse(stdout)
      return NextResponse.json(data)
    } catch {
      // If stdout isn't valid JSON, try to count draws from output file
      const fs = await import('fs')
      let totalDraws = 0
      try {
        const content = fs.readFileSync(outputFile, 'utf-8')
        totalDraws = content.split('\n').filter((line: string) => line.trim() && line.includes('||')).length
      } catch { /* ignore */ }

      if (totalDraws > 0 || code === 0) {
        return NextResponse.json({
          game,
          total_draws: totalDraws,
          data_file: outputFile,
        })
      }

      return NextResponse.json(
        {
          error: 'Failed to fetch draws',
          stderr: stderr?.slice(-500) || '',
          stdout: stdout?.slice(-500) || '',
        },
        { status: 500 }
      )
    }
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
