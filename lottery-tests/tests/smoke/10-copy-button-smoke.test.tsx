/**
 * Smoke test: CopyButton from @/components/lottery/CopyButton
 *
 * Verifies CopyButton renders with Copy icon, copies text on click,
 * shows "Скопировано" feedback, reverts after timeout, and handles
 * clipboard API unavailability.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react'

// Mock lucide-react Copy and Check icons
vi.mock('lucide-react', () => ({
  Copy: ({ className }: { className?: string }) => (
    <svg data-testid="icon-copy" className={className} />
  ),
  Check: ({ className }: { className?: string }) => (
    <svg data-testid="icon-check" className={className} />
  ),
}))

import { CopyButton } from '@/components/lottery/CopyButton'

function setupClipboard(writeText: ReturnType<typeof vi.fn>) {
  Object.assign(navigator, { clipboard: { writeText } })
  Object.assign(window, { isSecureContext: true })
}

describe('CopyButton', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders with Copy icon initially', () => {
    setupClipboard(vi.fn().mockResolvedValue(undefined))
    render(<CopyButton text="hello world" />)

    expect(screen.getByTestId('icon-copy')).toBeInTheDocument()
    expect(screen.queryByTestId('icon-check')).not.toBeInTheDocument()
    expect(screen.getByTitle('Копировать')).toBeInTheDocument()
    expect(screen.getByText('Копировать')).toBeInTheDocument()
  })

  it('click calls navigator.clipboard.writeText', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setupClipboard(writeText)

    render(<CopyButton text="test-text-123" />)
    fireEvent.click(screen.getByTitle('Копировать'))

    // Wait for the async handler to complete
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith('test-text-123')
    })
  })

  it('shows "Скопировано" after click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setupClipboard(writeText)

    render(<CopyButton text="hello" />)
    fireEvent.click(screen.getByTitle('Копировать'))

    // Wait for the state to update
    await waitFor(() => {
      expect(screen.getByTestId('icon-check')).toBeInTheDocument()
    })
    expect(screen.getByTitle('Скопировано')).toBeInTheDocument()
    expect(screen.getByText('Скопировано')).toBeInTheDocument()
    expect(screen.queryByTestId('icon-copy')).not.toBeInTheDocument()
  })

  it('reverts after 1500ms timeout', async () => {
    vi.useFakeTimers()
    const writeText = vi.fn().mockResolvedValue(undefined)
    setupClipboard(writeText)

    render(<CopyButton text="hello" />)
    fireEvent.click(screen.getByTitle('Копировать'))

    // Let the async handler complete and flush the 1500ms timeout
    await act(async () => {
      // Resolve the promise
      await Promise.resolve()
      // Run the setTimeout
      await vi.advanceTimersByTimeAsync(1500)
    })

    // Should revert to Copy icon
    expect(screen.getByTestId('icon-copy')).toBeInTheDocument()
    expect(screen.getByTitle('Копировать')).toBeInTheDocument()
  })

  it('handles clipboard API unavailable gracefully', async () => {
    // Remove clipboard API and secure context
    Object.assign(navigator, { clipboard: undefined })
    Object.assign(window, { isSecureContext: false })

    // Mock execCommand for the fallback path
    const execCommandMock = vi.fn().mockReturnValue(true)
    document.execCommand = execCommandMock

    render(<CopyButton text="fallback-text" />)
    const button = screen.getByRole('button')

    // The click should not throw an unhandled error
    expect(() => fireEvent.click(button)).not.toThrow()

    // The fallback path should have attempted execCommand
    expect(execCommandMock).toHaveBeenCalledWith('copy')

    // Component should still be functional after the click
    expect(button).toBeInTheDocument()
  })

  it('has sr-only text for accessibility', () => {
    setupClipboard(vi.fn().mockResolvedValue(undefined))

    render(<CopyButton text="test" />)

    const srText = screen.getByText('Копировать')
    expect(srText).toHaveClass('sr-only')
  })
})
