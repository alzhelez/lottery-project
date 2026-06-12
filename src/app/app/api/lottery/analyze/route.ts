import { NextResponse } from 'next/server'
import { runPythonScript, resolvePythonPath } from '@/lib/python-runner'
import { existsSync } from 'fs'
import { join } from 'path'

const ROOT = process.cwd()

export async function POST() {
  try {
    // Pre-check: verify Python is available
    const python = resolvePythonPath()
    const scriptPath = join(ROOT, 'python', 'analyze.py')
    if (!existsSync(scriptPath)) {
      return NextResponse.json(
        { error: `Python script not found at ${scriptPath}. Make sure python/analyze.py exists.` },
        { status: 500 },
      )
    }

    // Quick import test before running the full script
    const { execSync } = await import('child_process')
    try {
      execSync(`"${python}" -c "import numpy; import requests; print('OK')"`, {
        encoding: 'utf-8',
        timeout: 8000,
        stdio: ['pipe', 'pipe', 'pipe'],
      })
    } catch {
      return NextResponse.json(
        {
          error: `Python found but missing required packages.`,
          hint: `Run: pip install requests numpy scipy`,
          python_path: python,
        },
        { status: 500 },
      )
    }

    const { stdout, stderr, code } = await runPythonScript('analyze.py', [], {
      timeout: 300000, // 5 minutes
    })

    if (code !== 0) {
      return NextResponse.json(
        {
          error: `Script failed with code ${code}`,
          stderr: stderr?.slice(-500) || '',
          stdout: stdout?.slice(-200) || '',
        },
        { status: 500 },
      )
    }

    try {
      const data = JSON.parse(stdout)
      return NextResponse.json(data)
    } catch {
      return NextResponse.json(
        {
          error: 'Failed to parse script output',
          stdout: stdout?.slice(-500) || '',
          stderr: stderr?.slice(-500) || '',
        },
        { status: 500 },
      )
    }
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        hint: 'Make sure Python 3.10+ is installed and available in PATH. Required packages: pip install requests numpy scipy',
      },
      { status: 500 },
    )
  }
}
