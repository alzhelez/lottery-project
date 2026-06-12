import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ErrorBoundary } from '@/components/ErrorBoundary'

// Suppress React error logging
let consoleSpy: ReturnType<typeof vi.spyOn>
beforeEach(() => {
  consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => {
  consoleSpy.mockRestore()
})

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, className }: { children: React.ReactNode; onClick?: () => void; className?: string }) => (
    <button onClick={onClick} className={className} data-testid="reset-button">{children}</button>
  ),
}))

vi.mock('@/components/ui/card', () => ({
  Card: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className} data-testid="card">{children}</div>
  ),
  CardContent: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className} data-testid="card-content">{children}</div>
  ),
}))

vi.mock('lucide-react', () => ({
  AlertTriangle: () => <svg data-testid="alert-icon" />,
  RefreshCw: () => <svg data-testid="refresh-icon" />,
}))

function ThrowOnRender() {
  throw new Error('test error')
}

describe('ErrorBoundary', () => {
  it('normal render — children displayed when no error', () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">Hello World</div>
      </ErrorBoundary>
    )

    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('Hello World')).toBeInTheDocument()
  })

  it('error caught — shows "Что-то пошло не так" text', () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender />
      </ErrorBoundary>
    )

    expect(screen.getByText('Что-то пошло не так')).toBeInTheDocument()
  })

  it('custom fallback — fallback prop rendered instead of default UI', () => {
    render(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom Error</div>}>
        <ThrowOnRender />
      </ErrorBoundary>
    )

    expect(screen.getByTestId('custom-fallback')).toBeInTheDocument()
    expect(screen.getByText('Custom Error')).toBeInTheDocument()
    // Default UI should NOT be present
    expect(screen.queryByText('Что-то пошло не так')).not.toBeInTheDocument()
  })

  it('reset button — clicking "Попробовать снова" resets state', async () => {
    function ConditionalThrow({ shouldThrow }: { shouldThrow: boolean }) {
      if (shouldThrow) throw new Error('conditional error')
      return <div data-testid="recovered">Recovered!</div>
    }

    const { rerender } = render(
      <ErrorBoundary>
        <ConditionalThrow shouldThrow={true} />
      </ErrorBoundary>
    )

    // Error state
    expect(screen.getByText('Что-то пошло не так')).toBeInTheDocument()

    // First: update props so children no longer throw (ErrorBoundary still in error state)
    rerender(
      <ErrorBoundary>
        <ConditionalThrow shouldThrow={false} />
      </ErrorBoundary>
    )

    // ErrorBoundary still shows error UI because state hasn't changed
    expect(screen.getByText('Что-то пошло не так')).toBeInTheDocument()

    // Now click reset — clears hasError, re-renders children with updated props
    const resetButton = screen.getByTestId('reset-button')
    await userEvent.setup().click(resetButton)

    // Should show recovered content
    expect(screen.getByTestId('recovered')).toBeInTheDocument()
    expect(screen.getByText('Recovered!')).toBeInTheDocument()
    expect(screen.queryByText('Что-то пошло не так')).not.toBeInTheDocument()
  })
})
