/**
 * Smoke test: StepIndicator from @/components/lottery/StepIndicator
 *
 * Verifies all 4 steps render with correct labels, role="tablist",
 * disabled/enabled states, and aria-selected for active step.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// Mock lucide-react CheckCircle2 icon
vi.mock('lucide-react', () => ({
  CheckCircle2: ({ className }: { className?: string }) => (
    <svg data-testid="icon-check-circle" className={className} />
  ),
}))

import { StepIndicator } from '@/components/lottery/StepIndicator'
import type { GameAnalysis, PredictionResult } from '@/components/lottery/types'

const mockGameAnalysis: GameAnalysis = {
  name: '4x20',
  key: '4x20',
  score: 85,
  verdict: 'high',
  verdict_color: 'green',
  draws: 2500,
  hot_numbers: [3, 7, 12],
  cold_numbers: [1, 15, 19],
  chi2_p: 0.05,
  autocorr: 0.02,
  has_local_data: true,
}

const mockPredictionResult: PredictionResult = {
  status: 'success',
  game_format: '4x20',
  total_draws: 2500,
  prediction: { block1: [3, 7, 12, 18], block2: [1, 5, 9, 14] },
  consensus_strength: { block1: 0.8, block2: 0.7 },
  random_baseline: { block1: [], block2: [], expected_hits: 1.6 },
  cross_validation: {},
  backtest: {},
  monte_carlo: {},
  models_used: 133,
  analysis_methods: [],
}

/** Helper: get a step tab by its id (tab-1, tab-2, etc.) */
function getStepTab(n: number) {
  return document.getElementById(`tab-${n}`)!
}

describe('StepIndicator', () => {
  it('renders all 4 steps with correct labels', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={1}
        setStep={setStep}
        selectedGame={mockGameAnalysis}
        fetchDone={true}
        predictResult={mockPredictionResult}
      />,
    )

    // All 4 tab buttons should exist
    expect(getStepTab(1)).toBeInTheDocument()
    expect(getStepTab(2)).toBeInTheDocument()
    expect(getStepTab(3)).toBeInTheDocument()
    expect(getStepTab(4)).toBeInTheDocument()

    // Check Russian labels are visible (labels are in hidden span on mobile)
    expect(screen.getByText('Анализ')).toBeInTheDocument()
    expect(screen.getByText('Тиражи')).toBeInTheDocument()
    expect(screen.getByText('Прогноз')).toBeInTheDocument()
    expect(screen.getByText('Pipeline')).toBeInTheDocument()
  })

  it('container has role="tablist"', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={1}
        setStep={setStep}
        selectedGame={mockGameAnalysis}
        fetchDone={true}
        predictResult={mockPredictionResult}
      />,
    )

    expect(screen.getByRole('tablist')).toBeInTheDocument()
  })

  it('step 1 is never disabled', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={1}
        setStep={setStep}
        selectedGame={null}
        fetchDone={false}
        predictResult={null}
      />,
    )

    expect(getStepTab(1)).not.toBeDisabled()
  })

  it('step 2 is disabled when no game selected', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={1}
        setStep={setStep}
        selectedGame={null}
        fetchDone={false}
        predictResult={null}
      />,
    )

    expect(getStepTab(2)).toBeDisabled()
  })

  it('step 3 is disabled when fetch not done', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={2}
        setStep={setStep}
        selectedGame={mockGameAnalysis}
        fetchDone={false}
        predictResult={null}
      />,
    )

    expect(getStepTab(3)).toBeDisabled()
  })

  it('step 4 is disabled when no prediction result', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={3}
        setStep={setStep}
        selectedGame={mockGameAnalysis}
        fetchDone={true}
        predictResult={null}
      />,
    )

    expect(getStepTab(4)).toBeDisabled()
  })

  it('steps are enabled when prerequisites are met', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={1}
        setStep={setStep}
        selectedGame={mockGameAnalysis}
        fetchDone={true}
        predictResult={mockPredictionResult}
      />,
    )

    expect(getStepTab(1)).not.toBeDisabled()
    expect(getStepTab(2)).not.toBeDisabled()
    expect(getStepTab(3)).not.toBeDisabled()
    expect(getStepTab(4)).not.toBeDisabled()
  })

  it('active step has aria-selected="true"', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={3}
        setStep={setStep}
        selectedGame={mockGameAnalysis}
        fetchDone={true}
        predictResult={mockPredictionResult}
      />,
    )

    // Step 3 should be active
    expect(getStepTab(3)).toHaveAttribute('aria-selected', 'true')

    // Steps 1, 2 (done) and 4 (inactive) should not be selected
    expect(getStepTab(1)).toHaveAttribute('aria-selected', 'false')
    expect(getStepTab(2)).toHaveAttribute('aria-selected', 'false')
    expect(getStepTab(4)).toHaveAttribute('aria-selected', 'false')
  })

  it('clicking enabled step calls setStep', () => {
    const setStep = vi.fn()
    render(
      <StepIndicator
        step={1}
        setStep={setStep}
        selectedGame={mockGameAnalysis}
        fetchDone={true}
        predictResult={mockPredictionResult}
      />,
    )

    fireEvent.click(getStepTab(2))
    expect(setStep).toHaveBeenCalledWith(2)
  })
})
