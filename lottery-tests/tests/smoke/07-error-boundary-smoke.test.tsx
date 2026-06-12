/**
 * Smoke test: ErrorBoundary from @/components/ErrorBoundary
 *
 * Verifies the class component renders children normally, catches errors,
 * supports custom fallback, and resets correctly.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock shadcn UI components
vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, ...props }: Record<string, unknown>) => (
    <button onClick={onClick as React.MouseEventHandler} data-testid="mock-button" {...props}>
      {children as React.ReactNode}
    </button>
  ),
}))

vi.mock('@/components/ui/card', () => ({
  Card: ({ children, ...props }: Record<string, unknown>) => (
    <div data-testid="mock-card" {...props}>
      {children as React.ReactNode}
    </div>
  ),
  CardContent: ({ children, ...props }: Record<string, unknown>) => (
    <div data-testid="mock-card-content" {...props}>
      {children as React.ReactNode}
    </div>
  ),
}))

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  AlertTriangle: () => <svg data-testid="icon-alert-triangle" />,
  RefreshCw: () => <svg data-testid="icon-refresh-cw" />,
}))

// Import AFTER mocks are set up
import React from 'react'
import { ErrorBoundary } from '@/components/ErrorBoundary'

function GoodChild() {
  return <div data-testid="good-child">All good!</div>
}

function BadRenderChild() {
  throw new Error('Synchronous render error')
}

function EffectErrorChild() {
  const useEffect = React.useEffect
  useEffect(() => {
    throw new Error('useEffect error')
  }, [])
  return <div data-testid="effect-child">Mounting...</div>
}

// Suppress React error boundary console output
let consoleSpy: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('ErrorBoundary', () => {
  it('renders children normally when no error', () => {
    render(
      <ErrorBoundary>
        <GoodChild />
      </ErrorBoundary>,
    )
    expect(screen.getByTestId('good-child')).toBeInTheDocument()
    expect(screen.getByText('All good!')).toBeInTheDocument()
  })

  it('catches synchronous render errors', () => {
    render(
      <ErrorBoundary>
        <BadRenderChild />
      </ErrorBoundary>,
    )
    // The error boundary should catch the error and show its default fallback
    expect(screen.getByTestId('mock-card')).toBeInTheDocument()
    expect(screen.getByText(/пошло не так/i)).toBeInTheDocument()
  })

  it('catches errors in useEffect', () => {
    render(
      <ErrorBoundary>
        <EffectErrorChild />
      </ErrorBoundary>,
    )
    // After the effect throws, error boundary should activate
    expect(screen.getByTestId('mock-card')).toBeInTheDocument()
  })

  it('renders custom fallback prop when provided', () => {
    const customFallback = <div data-testid="custom-fallback">Custom error UI</div>

    render(
      <ErrorBoundary fallback={customFallback}>
        <BadRenderChild />
      </ErrorBoundary>,
    )
    expect(screen.getByTestId('custom-fallback')).toBeInTheDocument()
    expect(screen.getByText('Custom error UI')).toBeInTheDocument()
    // Default fallback should NOT be shown
    expect(screen.queryByTestId('mock-card')).not.toBeInTheDocument()
  })

  it('reset button clears the error state', async () => {
    // We need to conditionally render the bad child, so we use a wrapper
    let shouldThrow = true
    function ConditionalChild() {
      if (shouldThrow) throw new Error('boom')
      return <div data-testid="recovered">Recovered!</div>
    }

    render(
      <ErrorBoundary>
        <ConditionalChild />
      </ErrorBoundary>,
    )

    // Error is shown
    expect(screen.getByTestId('mock-card')).toBeInTheDocument()

    // Fix the error
    shouldThrow = false

    // Click the reset button
    const resetButton = screen.getByTestId('mock-button')
    await act(async () => {
      await userEvent.click(resetButton)
    })

    // Error should be cleared and children re-render
    expect(screen.getByTestId('recovered')).toBeInTheDocument()
    expect(screen.queryByTestId('mock-card')).not.toBeInTheDocument()
  })
})
