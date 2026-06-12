import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { usePolling } from '@/hooks/usePolling'

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('stops after maxRetries — pollFn should not be called more than maxRetries times', async () => {
    const maxRetries = 3
    const delayMs = 1000
    const pollFn = vi.fn().mockResolvedValue(true) // always continue

    const { result } = renderHook(() =>
      usePolling({ maxRetries, delayMs })
    )

    act(() => {
      result.current.startPolling(pollFn)
    })

    // After initial call (synchronous), we need to advance timers for subsequent calls
    // First poll() is called synchronously. It increments retries to 1, then waits delayMs.
    // After delayMs, pollFn is called. If true, poll() is called again (retries=2), waits delayMs, etc.
    // With maxRetries=3: retries go 1,2,3. After retries=3, pollFn is called, if true, poll() is called
    // but retries (now 4) >= maxRetries (3), so it returns.
    // So pollFn is called maxRetries times (3 calls).

    await act(async () => {
      // First delay completes → pollFn call 1 → poll() again → second delay
      vi.advanceTimersByTime(delayMs)
      await Promise.resolve()
    })
    await act(async () => {
      // Second delay completes → pollFn call 2 → poll() again → third delay
      vi.advanceTimersByTime(delayMs)
      await Promise.resolve()
    })
    await act(async () => {
      // Third delay completes → pollFn call 3 → poll() called but retries(4) >= maxRetries(3) → stop
      vi.advanceTimersByTime(delayMs)
      await Promise.resolve()
    })

    expect(pollFn).toHaveBeenCalledTimes(maxRetries)
  })

  it('cancellation via versionRef — incrementing versionRef.current stops polling', async () => {
    const delayMs = 1000
    const pollFn = vi.fn().mockResolvedValue(true)

    const { result } = renderHook(() =>
      usePolling({ maxRetries: 10, delayMs })
    )

    act(() => {
      result.current.startPolling(pollFn)
    })

    // Cancel by bumping version
    act(() => {
      result.current.versionRef.current++
    })

    // Advance timers well past several polling cycles
    await act(async () => {
      vi.advanceTimersByTime(delayMs * 5)
      await Promise.resolve()
    })

    // pollFn should have been called 0 times because the version check happens
    // BEFORE the first call — poll() is invoked synchronously, retries becomes 1,
    // then we await setTimeout. But we cancelled before the setTimeout resolved.
    // Actually: poll() is sync, retries=1, awaits setTimeout. When timer fires,
    // versionRef.current !== v, so pollFn is never called.
    expect(pollFn).toHaveBeenCalledTimes(0)
  })

  it('error handling — onError callback called when pollFn rejects', async () => {
    const delayMs = 1000
    const error = new Error('network failure')
    const pollFn = vi.fn().mockRejectedValue(error)
    const onError = vi.fn()

    const { result } = renderHook(() =>
      usePolling({ maxRetries: 10, delayMs, onError })
    )

    act(() => {
      result.current.startPolling(pollFn)
    })

    // Advance past the first delay so pollFn is called
    await act(async () => {
      vi.advanceTimersByTime(delayMs)
      await Promise.resolve()
    })

    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledWith(error)
  })

  it('successful completion — pollFn returns false, polling stops', async () => {
    const delayMs = 1000
    const pollFn = vi.fn().mockResolvedValue(false)

    const { result } = renderHook(() =>
      usePolling({ maxRetries: 10, delayMs })
    )

    act(() => {
      result.current.startPolling(pollFn)
    })

    // Advance past the first delay
    await act(async () => {
      vi.advanceTimersByTime(delayMs)
      await Promise.resolve()
    })

    // pollFn called once, returns false → polling stops
    expect(pollFn).toHaveBeenCalledTimes(1)

    // Advance more — should NOT be called again
    await act(async () => {
      vi.advanceTimersByTime(delayMs * 5)
      await Promise.resolve()
    })

    expect(pollFn).toHaveBeenCalledTimes(1)
  })
})
