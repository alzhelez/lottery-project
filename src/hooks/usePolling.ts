'use client'

import { useRef, useCallback } from 'react'

interface UsePollingOptions {
  maxRetries?: number
  delayMs?: number
  /** Callback when a network error stops polling (default: silent) */
  onError?: (error: Error) => void
}

interface UsePollingReturn {
  startPolling: (pollFn: () => Promise<boolean>) => void
  versionRef: React.MutableRefObject<number>
}

export function usePolling(options: UsePollingOptions = {}): UsePollingReturn {
  const { maxRetries = 60, delayMs = 5000, onError } = options
  const versionRef = useRef(0)

  const startPolling = useCallback((pollFn: () => Promise<boolean>) => {
    versionRef.current++ // v39.2.1: cancel any existing poll
    let retries = 0
    const v = versionRef.current

    const poll = async () => {
      if (versionRef.current !== v) return // cancelled
      retries++
      if (retries > maxRetries) return
      await new Promise(r => setTimeout(r, delayMs))
      if (versionRef.current !== v) return // cancelled

      try {
        const shouldContinue = await pollFn()
        if (versionRef.current !== v) return
        if (shouldContinue) poll()
      } catch (err) {
        // v39.2.0: Network error — notify caller but CONTINUE polling.
        // God Mode runs server-side in the background — even if a poll request
        // fails (network error, timeout, server compilation via Turbopack HMR),
        // the server continues processing. Stopping polling would lose progress.
        // Only stop if maxRetries is exhausted (checked at top of next iteration).
        if (versionRef.current !== v) return
        if (onError) {
          onError(err instanceof Error ? err : new Error(String(err)))
        }
        // Schedule next poll instead of stopping
        poll()
      }
    }

    poll()
  }, [maxRetries, delayMs, onError])

  return { startPolling, versionRef }
}
