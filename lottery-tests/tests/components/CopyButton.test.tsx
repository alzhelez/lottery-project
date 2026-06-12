import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { CopyButton } from '@/components/lottery/CopyButton'

let mockWriteText: ReturnType<typeof vi.fn>

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Copy: ({ className }: { className?: string }) => (
    <svg data-testid="copy-icon" className={className} />
  ),
  Check: ({ className }: { className?: string }) => (
    <svg data-testid="check-icon" className={className} />
  ),
}))

describe('CopyButton', () => {
  let originalClipboard: unknown

  beforeEach(() => {
    vi.useFakeTimers()
    mockWriteText = vi.fn().mockResolvedValue(undefined)
    originalClipboard = navigator.clipboard
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: mockWriteText },
      writable: true,
      configurable: true,
    })
    Object.defineProperty(window, 'isSecureContext', {
      value: true,
      writable: true,
      configurable: true,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    Object.defineProperty(navigator, 'clipboard', {
      value: originalClipboard,
      writable: true,
      configurable: true,
    })
  })

  it('renders with Copy icon initially', () => {
    render(<CopyButton text="hello" />)

    expect(screen.getByTestId('copy-icon')).toBeInTheDocument()
    expect(screen.queryByTestId('check-icon')).not.toBeInTheDocument()
  })

  it('clicking calls navigator.clipboard.writeText with correct text', async () => {
    render(<CopyButton text="test-content" />)

    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
      // Flush microtasks so the async handler completes
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(mockWriteText).toHaveBeenCalledTimes(1)
    expect(mockWriteText).toHaveBeenCalledWith('test-content')
  })

  it('after copy, shows "Скопировано" sr-only text', async () => {
    render(<CopyButton text="hello" />)

    expect(screen.getByText('Копировать')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
      // Flush microtasks to resolve clipboard.writeText and setCopied(true)
      await Promise.resolve()
      await Promise.resolve()
    })

    // Do NOT advance timers — we want to catch the copied state before the 1500ms reverts it
    expect(screen.getByText('Скопировано')).toBeInTheDocument()
    expect(screen.getByTestId('check-icon')).toBeInTheDocument()
  })

  it('after 1500ms timeout, reverts to "Копировать"', async () => {
    render(<CopyButton text="hello" />)

    // Click and flush to get into copied state
    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
      await Promise.resolve()
      await Promise.resolve()
    })

    // Shows copied state
    expect(screen.getByText('Скопировано')).toBeInTheDocument()
    expect(screen.getByTestId('check-icon')).toBeInTheDocument()

    // Advance past the 1500ms timeout
    await act(async () => {
      vi.advanceTimersByTime(1500)
    })

    // Should revert
    expect(screen.getByText('Копировать')).toBeInTheDocument()
    expect(screen.getByTestId('copy-icon')).toBeInTheDocument()
  })

  it('handles clipboard API unavailable gracefully', async () => {
    // Remove clipboard API and set insecure context
    Object.defineProperty(navigator, 'clipboard', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    Object.defineProperty(window, 'isSecureContext', {
      value: false,
      writable: true,
      configurable: true,
    })

    // jsdom doesn't have document.execCommand — define it so the fallback path works
    document.execCommand = vi.fn().mockReturnValue(true) as unknown as typeof document.execCommand

    render(<CopyButton text="fallback-text" />)

    // Should not throw even when clipboard API is unavailable
    await act(async () => {
      fireEvent.click(screen.getByRole('button'))
      // Flush microtasks for the fallback path
      await Promise.resolve()
      await Promise.resolve()
    })

    // Should show copied state (fallback succeeded silently)
    expect(screen.getByText('Скопировано')).toBeInTheDocument()
    expect(screen.getByTestId('check-icon')).toBeInTheDocument()
  })
})
