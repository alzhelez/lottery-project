/**
 * Smoke test: usePolling hook from @/hooks/usePolling
 *
 * Verifies startPolling calls pollFn, stops after maxRetries,
 * versionRef cancellation works, handles async errors gracefully,
 * and doesn't leak timers.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

import { usePolling } from '@/hooks/usePolling'

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('startPolling calls pollFn', async () => {
    const pollFn = vi.fn().mockResolvedValue(false)
    const { result } = renderHook(() => usePolling({ delayMs: 100 }))

    act(() => {
      result.current.startPolling(pollFn)
    })

    // Wait for the delay
    await act(async () => {
      await vi.advanceTimersByTimeAsync(150)
    })

    expect(pollFn).toHaveBeenCalledTimes(1)
  })

  it('stops after maxRetries', async () => {
    const pollFn = vi.fn().mockResolvedValue(true) // always continue
    const { result } = renderHook(() => usePolling({ maxRetries: 3, delayMs: 100 }))

    act(() => {
      result.current.startPolling(pollFn)
    })

    // Advance through 3 retries
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350)
    })

    expect(pollFn).toHaveBeenCalledTimes(3)

    // Advance more — should NOT call again
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })

    expect(pollFn).toHaveBeenCalledTimes(3)
  })

  it('versionRef cancellation works immediately', async () => {
    const pollFn = vi.fn().mockResolvedValue(true)
    const onError = vi.fn()
    const { result } = renderHook(() => usePolling({ maxRetries: 100, delayMs: 100, onError }))

    act(() => {
      result.current.startPolling(pollFn)
    })

    // Let one poll go through
    await act(async () => {
      await vi.advanceTimersByTimeAsync(150)
    })
    expect(pollFn).toHaveBeenCalledTimes(1)

    // Cancel by incrementing version
    act(() => {
      result.current.versionRef.current++
    })

    // Advance time — no more polls should happen
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })

    expect(pollFn).toHaveBeenCalledTimes(1)
  })

  it('handles async errors gracefully', async () => {
    const pollFn = vi.fn().mockRejectedValue(new Error('Network error'))
    const onError = vi.fn()
    const { result } = renderHook(() => usePolling({ maxRetries: 5, delayMs: 100, onError }))

    act(() => {
      result.current.startPolling(pollFn)
    })

    // Let the first poll run and fail
    await act(async () => {
      await vi.advanceTimersByTimeAsync(150)
    })

    expect(pollFn).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledWith(expect.any(Error))

    // Polling should stop after error
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })

    expect(pollFn).toHaveBeenCalledTimes(1)
  })

  it('multiple sequential polls do not leak timers', async () => {
    const pollFn1 = vi.fn().mockResolvedValue(false)
    const pollFn2 = vi.fn().mockResolvedValue(false)
    const onError = vi.fn()
    const { result } = renderHook(() => usePolling({ maxRetries: 10, delayMs: 50, onError }))

    // Start first poll
    act(() => {
      result.current.startPolling(pollFn1)
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(80)
    })
    expect(pollFn1).toHaveBeenCalledTimes(1)

    // Cancel first and start second
    act(() => {
      result.current.versionRef.current++
      result.current.startPolling(pollFn2)
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(80)
    })
    expect(pollFn2).toHaveBeenCalledTimes(1)

    // pollFn1 should not have been called again
    expect(pollFn1).toHaveBeenCalledTimes(1)
  })

  it('stops polling when pollFn returns false', async () => {
    const pollFn = vi.fn()
      .mockResolvedValueOnce(true)  // continue
      .mockResolvedValueOnce(true)  // continue
      .mockResolvedValueOnce(false) // stop

    const { result } = renderHook(() => usePolling({ maxRetries: 100, delayMs: 50 }))

    act(() => {
      result.current.startPolling(pollFn)
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })

    expect(pollFn).toHaveBeenCalledTimes(3)

    // No more calls after stopping
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })

    expect(pollFn).toHaveBeenCalledTimes(3)
  })
})
