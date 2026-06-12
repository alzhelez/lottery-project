import { spawn, execSync } from 'child_process'
import { join } from 'path'
import { existsSync } from 'fs'

const ROOT = process.cwd()
const IS_WIN = process.platform === 'win32'

// ── Python path resolution (memoized) ───────────────────────────────────────

let _cachedPythonPath: string | null = null
let _pythonResolved = false

/**
 * Find a working Python executable that has numpy, and requests.
 * Memoized after first successful resolution.
 *
 * Search order:
 *  1. Sandboxed /home/z/.venv/bin/python3 (Linux dev environment)
 *  2. USERPROFILE\.venv\Scripts\python.exe  (Windows local)
 *  3. Python virtual envs from common locations
 *  4. System PATH (using `where` on Windows, `which` on Linux)
 */
export function resolvePythonPath(): string {
  if (_pythonResolved && _cachedPythonPath) return _cachedPythonPath

  const candidates: string[] = []

  // --- Linux / macOS sandbox paths ---
  candidates.push(
    '/home/z/.venv/bin/python3',
    '/home/z/.venv/bin/python',
  )
  if (process.env.HOME) {
    candidates.push(
      join(process.env.HOME, '.venv', 'bin', 'python3'),
      join(process.env.HOME, '.venv', 'bin', 'python'),
      join(process.env.HOME, '.local', 'bin', 'python3'),
    )
  }
  if (process.env.CONDA_PREFIX) {
    candidates.push(join(process.env.CONDA_PREFIX, 'bin', 'python3'))
  }

  // --- Windows local paths ---
  if (process.env.USERPROFILE) {
    candidates.push(
      join(process.env.USERPROFILE, '.venv', 'Scripts', 'python.exe'),
      join(process.env.USERPROFILE, '.venv', 'Scripts', 'python3.exe'),
    )
  }
  // LOCALAPPDATA (common for pip --user installs on Windows)
  if (process.env.LOCALAPPDATA) {
    candidates.push(
      join(process.env.LOCALAPPDATA, 'Programs', 'Python', 'Python312', 'python.exe'),
      join(process.env.LOCALAPPDATA, 'Programs', 'Python', 'Python311', 'python.exe'),
      join(process.env.LOCALAPPDATA, 'Programs', 'Python', 'Python310', 'python.exe'),
    )
  }

  // Check all static candidates
  for (const candidate of candidates) {
    if (!existsSync(candidate)) continue
    if (testPython(candidate)) return candidate
  }

  // --- Fallback: search system PATH ---
  const cmds = IS_WIN
    ? ['python', 'python3', 'py']           // `py` is the Windows Launcher
    : ['python3', 'python']

  for (const cmd of cmds) {
    const resolved = findOnPath(cmd)
    if (resolved && testPython(resolved)) return resolved
  }

  // Nothing found — don't set _pythonResolved to allow retry on next call
  console.warn(
    '[api] WARNING: No Python with required packages found.\n' +
    '  Install Python 3.10+ from https://python.org  (check "Add to PATH" during install)\n' +
    '  Then run: pip install requests numpy scipy pandas plotly',
  )
  _cachedPythonPath = IS_WIN ? 'python' : 'python3'
  _pythonResolved = true // v39.2.1: prevent re-scanning on every call
  return _cachedPythonPath
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Test that a Python binary can import the required packages. */
function testPython(python: string): boolean {
  try {
    const result = execSync(
      `"${python}" -c "import numpy; import requests; import pandas; import plotly; print('OK')"`,
      { encoding: 'utf-8', timeout: 8000, stdio: ['pipe', 'pipe', 'pipe'] },
    ).trim()
    if (result === 'OK') {
      _cachedPythonPath = python
      _pythonResolved = true
      console.log(`[api] Python resolved: ${python}`)
      return true
    }
  } catch {
    // Skip
  }
  return false
}

/** Resolve a command name to a full path using `where` (Win) or `which` (Unix). */
function findOnPath(cmd: string): string | null {
  try {
    const tool = IS_WIN ? 'where' : 'which'
    const redirect = IS_WIN ? '2>nul' : '2>/dev/null'
    const result = execSync(`${tool} ${cmd} ${redirect}`, {
      encoding: 'utf-8',
      timeout: 3000,
      shell: IS_WIN ? 'cmd.exe' : undefined,
    }).trim()
    if (result) {
      // `where` may return multiple lines; take the first
      return result.split(/[\r\n]+/)[0]
    }
  } catch {
    // Not found
  }
  return null
}

// ── Script runner ───────────────────────────────────────────────────────────

/**
 * Run a Python script asynchronously and return its output.
 */
export function runPythonScript(
  scriptName: string,
  args: string[],
  options?: { timeout?: number },
): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolve, reject) => {
    const python = resolvePythonPath()
    const scriptPath = join(ROOT, 'python', scriptName)
    const timeout = options?.timeout ?? 600000 // 10 minutes default

    // Validate that the script exists before spawning
    if (!existsSync(scriptPath)) {
      return reject(new Error(`Python script not found: ${scriptPath}`))
    }

    let child

    if (IS_WIN) {
      // On Windows, use shell:true to support PATH-only python commands.
      // Embed the full command + args in a single string (avoid DEP0190 warning
      // about passing args array with shell:true).
      // v39.2.1: Escape double-quotes in args to prevent shell injection on Windows
      const escapedArgs = args.map(a => '"' + a.replace(/"/g, '\\"') + '"').join(' ')
      const fullCmd = '"' + python + '" "' + scriptPath + '" ' + escapedArgs
      child = spawn(fullCmd, [], {
        cwd: ROOT,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        stdio: ['pipe', 'pipe', 'pipe'],
        shell: true,
        windowsHide: true,
      })
    } else {
      // On Linux/macOS, use detached:true to create a new process group.
      // This allows us to kill the entire process group (main Python + any
      // subprocesses like numpy threads) with a single signal, preventing
      // orphan processes from keeping pipes open and causing hangs.
      child = spawn(python, [scriptPath, ...args], {
        cwd: ROOT,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        stdio: ['pipe', 'pipe', 'pipe'],
        detached: true,
      })
    }

    let stdout = ''
    let stderr = ''
    let killed = false

    // Timeout handler: SIGTERM first, then SIGKILL as fallback
    const timer = setTimeout(() => {
      killed = true
      try {
        // On Linux with detached:true, child.pid is the process group leader.
        // Kill the entire process group to ensure numpy/scipy subprocesses are
        // also terminated, preventing pipe-held hangs.
        if (child.pid && !IS_WIN) {
          process.kill(-child.pid, 'SIGTERM')
        } else {
          child.kill('SIGTERM')
        }
      } catch {
        try { child.kill('SIGTERM') } catch { /* already dead */ }
      }
      // Fallback: SIGKILL after 3 seconds if process still alive
      const forceKillTimer = setTimeout(() => {
        try {
          if (child.pid && !IS_WIN) {
            process.kill(-child.pid, 'SIGKILL')
          } else {
            child.kill('SIGKILL')
          }
        } catch { /* already dead */ }
      }, 3000)
      // Clear force-kill timer on either exit or close event
      const cleanupForceKill = () => clearTimeout(forceKillTimer)
      child.on('exit', cleanupForceKill)
      child.on('close', cleanupForceKill)
    }, timeout)

    child.stdout.on('data', (data: Buffer) => {
      stdout += data.toString('utf-8')
    })

    child.stderr.on('data', (data: Buffer) => {
      stderr += data.toString('utf-8')
    })

    child.on('error', (err) => {
      clearTimeout(timer)
      if (!resolved) {
        resolved = true
        reject(err)
      }
    })

    // v38.2.3: Track resolution to prevent double-resolve.
    // Use both 'exit' and 'close' events — resolve on whichever fires first.
    // 'exit' fires when the process terminates (even if pipes are still open).
    // 'close' fires when all stdio streams are closed.
    // With detached:true, orphan subprocesses could keep pipes open, so 'close'
    // might never fire — 'exit' provides a reliable fallback.
    let resolved = false

    const resolveResult = (code: number | null) => {
      clearTimeout(timer)
      if (resolved) return
      resolved = true
      resolve({ stdout, stderr, code })
    }

    child.on('exit', (code) => {
      resolveResult(code)
    })

    child.on('close', (code) => {
      resolveResult(code)
    })
  })
}
