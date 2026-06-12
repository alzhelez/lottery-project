const _requestCounts: Record<string, { count: number; resetTime: number }> = {}
const MAX_ENTRIES = 500

interface RateLimitResult {
  allowed: boolean
  remaining: number
  resetIn: number
}

/** Evict expired entries to prevent unbounded memory growth */
function _evict(): void {
  const now = Date.now()
  const keys = Object.keys(_requestCounts)
  // Remove expired entries first
  for (const key of keys) {
    if (now > _requestCounts[key].resetTime) {
      delete _requestCounts[key]
    }
  }
  // If still over limit, remove oldest entries
  const remaining = Object.keys(_requestCounts)
  if (remaining.length > MAX_ENTRIES) {
    remaining.sort((a, b) => _requestCounts[a].resetTime - _requestCounts[b].resetTime)
    for (let i = 0; i < remaining.length - MAX_ENTRIES; i++) {
      delete _requestCounts[remaining[i]]
    }
  }
}

/**
 * Simple in-memory rate limiter with automatic eviction.
 * @param key - unique key (e.g., 'predict-4x20')
 * @param maxRequests - max requests in the window
 * @param windowMs - time window in milliseconds
 */
export function rateLimit(key: string, maxRequests: number = 5, windowMs: number = 60_000): RateLimitResult {
  const now = Date.now()
  const entry = _requestCounts[key]

  if (!entry || now > entry.resetTime) {
    _requestCounts[key] = { count: 1, resetTime: now + windowMs }
    _evict()
    return { allowed: true, remaining: maxRequests - 1, resetIn: windowMs }
  }

  if (entry.count >= maxRequests) {
    const resetIn = entry.resetTime - now
    return { allowed: false, remaining: 0, resetIn }
  }

  entry.count++
  return { allowed: true, remaining: maxRequests - entry.count, resetIn: entry.resetTime - now }
}
