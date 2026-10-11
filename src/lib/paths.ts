import path from 'node:path'

export const PROJECT_ROOT = process.cwd()

export function dataDir(): string {
  return process.env.LOTTERY_DATA_DIR || path.join(PROJECT_ROOT, 'data')
}

export function drawsFile(slug: string): string {
  return path.join(dataDir(), 'draws', `draws_${slug}.txt`)
}

export function resultsFile(slug: string | null, name: string): string {
  return slug ? path.join(dataDir(), 'results', slug, name) : path.join(dataDir(), 'results', name)
}

const SLUG_RE = /^[a-z0-9_-]{1,40}$/

export function isValidSlug(slug: unknown): slug is string {
  return typeof slug === 'string' && SLUG_RE.test(slug)
}
