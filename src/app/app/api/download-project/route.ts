import { execSync } from 'child_process'
import { accessSync, constants, mkdirSync, cpSync, writeFileSync, rmSync } from 'fs'
import { readFile, unlink } from 'fs/promises'
import { NextResponse } from 'next/server'
import { join } from 'path'

const ARCHIVE_PATH = '/tmp/lottery-project.tar.gz'
const STAGING_DIR = '/tmp/lottery-project-staging'
const PROJECT_ROOT = '/home/z/my-project'
const ARCHIVE_DIR = 'lottery-project'

export async function GET() {
  try {
    // Verify project root exists
    accessSync(PROJECT_ROOT, constants.R_OK)

    // Clean up any previous staging
    rmSync(STAGING_DIR, { recursive: true, force: true })

    // Create staging directory with lottery-project/ wrapper
    const targetDir = join(STAGING_DIR, ARCHIVE_DIR)
    mkdirSync(targetDir, { recursive: true })

    // Files/dirs to copy
    const candidates = [
      'src/', 'python/',
      'next.config.ts', 'tailwind.config.ts', 'tsconfig.json',
      'postcss.config.mjs', 'postcss.config.js',
      'prisma/', 'Caddyfile', 'public/',
    ]
    for (const item of candidates) {
      try {
        accessSync(join(PROJECT_ROOT, item), constants.R_OK)
        cpSync(join(PROJECT_ROOT, item), join(targetDir, item), { recursive: true })
      } catch {
        // skip missing items
      }
    }

    // Copy upload/ files into python/ as fallback (if not already there)
    const uploadFiles = [
      'stoloto_analyzer_v3.py',
      'lottery_pipeline.py',
      'lp_v130_app.py',
      'fetch_draws.py',
      'stoloto_analysis_v3.json',
    ]
    for (const f of uploadFiles) {
      try {
        const src = join(PROJECT_ROOT, 'upload', f)
        const dst = join(targetDir, 'python', f)
        accessSync(src, constants.R_OK)
        // Only copy if not already in python/ (from the recursive copy above)
        try { accessSync(dst, constants.R_OK) } catch {
          cpSync(src, dst)
        }
      } catch {
        // skip missing items
      }
    }

    // Create a Windows/npm-friendly package.json
    const pkg = JSON.parse(await readFile(join(PROJECT_ROOT, 'package.json'), 'utf-8'))
    pkg.scripts = {
      dev: 'next dev -p 3000',
      build: 'next build',
      start: 'next start',
      lint: 'eslint .',
      'db:push': 'prisma db push',
      'db:generate': 'prisma generate',
    }
    // Remove dev-only deps that aren't needed for the user
    if (pkg.devDependencies) {
      delete pkg.devDependencies['bun-types']
      // Move critical runtime deps from devDependencies to dependencies
      if (pkg.devDependencies['tw-animate-css'] && !pkg.dependencies['tw-animate-css']) {
        pkg.dependencies['tw-animate-css'] = pkg.devDependencies['tw-animate-css']
        delete pkg.devDependencies['tw-animate-css']
      }
    }
    writeFileSync(join(targetDir, 'package.json'), JSON.stringify(pkg, null, 2) + '\n')

    // Create tar.gz with the wrapper directory
    const excludes = '--exclude=node_modules --exclude=.next --exclude=.git --exclude=*.db --exclude=__pycache__ --exclude=*.bak'
    execSync(`cd ${STAGING_DIR} && tar czf ${ARCHIVE_PATH} ${excludes} ${ARCHIVE_DIR}`)

    const fileBuffer = await readFile(ARCHIVE_PATH)

    // Clean up temp files asynchronously
    unlink(ARCHIVE_PATH).catch(() => {})
    rmSync(STAGING_DIR, { recursive: true, force: true })

    // Use octet-stream to force download in all browsers
    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': 'attachment; filename="lottery-project.tar.gz"',
        'Content-Length': String(fileBuffer.length),
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      },
    })
  } catch (error) {
    console.error('Failed to create project archive:', error)
    return NextResponse.json(
      { error: `Archive creation failed: ${error instanceof Error ? error.message : 'Unknown error'}` },
      { status: 500 }
    )
  }
}
