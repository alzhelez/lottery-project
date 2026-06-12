import { NextResponse } from 'next/server'
import { runPythonScript } from '@/lib/python-runner'

/** Helper to create a JSON response with proper headers. */
function json(data: unknown, status = 200) {
  return NextResponse.json(data, {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  })
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const game = searchParams.get('game') || '4x20'
  const maxDraws = parseInt(searchParams.get('max_draws') || '200', 10)

  if (!game) {
    return json({ status: 'error', error: 'Missing game parameter' }, 400)
  }

  try {
    const { stdout, stderr, code } = await runPythonScript(
      'api_wrapper.py',
      ['draws', '--game', game, '--max-draws', String(maxDraws)],
      { timeout: 60000 },
    )

    if (code !== 0) {
      return json(
        {
          status: 'error',
          error: `Script failed with code ${code}`,
          stderr: stderr?.slice(-500) || '',
          stdout: stdout?.slice(-200) || '',
        },
        500,
      )
    }

    try {
      const data = JSON.parse(stdout)
      if (data.status === 'error') {
        return json(data, 500)
      }
      return json(data)
    } catch {
      return json(
        {
          status: 'error',
          error: 'Failed to parse script output',
          stdout: stdout?.slice(-500) || '',
          stderr: stderr?.slice(-500) || '',
        },
        500,
      )
    }
  } catch (error) {
    return json(
      { status: 'error', error: error instanceof Error ? error.message : 'Unknown error' },
      500,
    )
  }
}
