import { NextResponse } from 'next/server'
import { join } from 'path'
import { tmpdir } from 'os'
import { existsSync, statSync } from 'fs'
import { validateGameId, validateFilePath } from '@/lib/api-utils'
import { runPythonScript, resolvePythonPath } from '@/lib/python-runner'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { game, data_file } = body

    const gameErr = validateGameId(game)
    if (gameErr) {
      return NextResponse.json({ error: gameErr }, { status: 400 })
    }

    const file = data_file || (game ? join(tmpdir(), `draws_${game}.txt`) : null)

    if (file) {
      const fileErr = validateFilePath(file)
      if (fileErr) {
        return NextResponse.json({ error: fileErr }, { status: 400 })
      }
    }

    if (!file) {
      return NextResponse.json(
        { error: 'Missing "data_file" or "game" parameter in request body' },
        { status: 400 }
      )
    }

    // Pre-check: verify file exists and has content
    if (!existsSync(file)) {
      return NextResponse.json(
        { error: `Draw data file not found: ${file}. Please fetch draws first.` },
        { status: 400 }
      )
    }
    const fileStat = statSync(file)
    if (fileStat.size === 0) {
      return NextResponse.json(
        { error: `Draw data file is empty: ${file}. Please fetch draws first.` },
        { status: 400 }
      )
    }

    const { stdout, stderr, code } = await runPythonScript('predict.py', ['--file', file, '--no-cv', '--no-mc', '--batch-step', '200'], {
      timeout: 600000, // 10 minutes
    })

    if (code !== 0) {
      const python = resolvePythonPath()
      return NextResponse.json(
        {
          error: `Script failed with code ${code}`,
          stderr: stderr?.slice(-500) || '',
          python_path: python,
          hint: code === 9009 ? 'Python not found. Install Python 3.10+ from python.org and check "Add to PATH".' : undefined,
        },
        { status: 500 }
      )
    }

    try {
      const data = JSON.parse(stdout)
      return NextResponse.json(data)
    } catch {
      return NextResponse.json(
        { error: 'Failed to parse script output', stdout: stdout?.slice(-1000) || '' },
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
