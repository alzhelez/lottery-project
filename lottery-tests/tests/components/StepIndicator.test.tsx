import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { StepIndicator } from '@/components/lottery/StepIndicator'
import type { GameAnalysis, PredictionResult } from '@/components/lottery/types'

vi.mock('lucide-react', () => ({
  CheckCircle2: () => <svg data-testid="check-icon" />,
}))

const mockGame: GameAnalysis = {
  name: '4x20',
  key: '4x20',
  score: 10,
  verdict: 'ok',
  verdict_color: 'green',
  draws: 100,
  hot_numbers: [],
  cold_numbers: [],
  chi2_p: null,
  autocorr: null,
}

const mockPredict: PredictionResult = {
  status: 'ok',
  game_format: '4x4',
  total_draws: 100,
  prediction: { block1: [1, 2, 3, 4], block2: [1, 2, 3, 4] },
  consensus_strength: { block1: 0, block2: 0 },
  random_baseline: { block1: [], block2: [], expected_hits: 0 },
  cross_validation: {},
  backtest: {},
  monte_carlo: {},
  models_used: 133,
  analysis_methods: [],
}

const defaultProps = {
  step: 1 as const,
  setStep: vi.fn(),
  selectedGame: null as GameAnalysis | null,
  fetchDone: false,
  predictResult: null as PredictionResult | null,
}

describe('StepIndicator', () => {
  it('renders 4 tabs with correct labels', () => {
    render(<StepIndicator {...defaultProps} />)

    expect(screen.getByRole('tab', { name: /Анализ/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Тиражи/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Прогноз/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Pipeline/ })).toBeInTheDocument()
  })

  it('has role="tablist" on container', () => {
    render(<StepIndicator {...defaultProps} />)

    expect(screen.getByRole('tablist')).toBeInTheDocument()
  })

  it('tab "Тиражи" disabled when selectedGame=null', () => {
    render(<StepIndicator {...defaultProps} />)

    const tab2 = screen.getByRole('tab', { name: /Тиражи/ })
    expect(tab2).toBeDisabled()
  })

  it('tab "Тиражи" enabled when selectedGame provided', () => {
    render(<StepIndicator {...defaultProps} selectedGame={mockGame} />)

    const tab2 = screen.getByRole('tab', { name: /Тиражи/ })
    expect(tab2).not.toBeDisabled()
  })

  it('tab "Прогноз" disabled when fetchDone=false', () => {
    render(<StepIndicator {...defaultProps} fetchDone={false} />)

    const tab3 = screen.getByRole('tab', { name: /Прогноз/ })
    expect(tab3).toBeDisabled()
  })

  it('tab "Прогноз" enabled when fetchDone=true', () => {
    render(<StepIndicator {...defaultProps} fetchDone={true} />)

    const tab3 = screen.getByRole('tab', { name: /Прогноз/ })
    expect(tab3).not.toBeDisabled()
  })

  it('tab "Pipeline" disabled when predictResult=null', () => {
    render(<StepIndicator {...defaultProps} />)

    const tab4 = screen.getByRole('tab', { name: /Pipeline/ })
    expect(tab4).toBeDisabled()
  })

  it('tab "Pipeline" enabled when predictResult provided', () => {
    render(<StepIndicator {...defaultProps} predictResult={mockPredict} />)

    const tab4 = screen.getByRole('tab', { name: /Pipeline/ })
    expect(tab4).not.toBeDisabled()
  })

  it('active tab has aria-selected=true', () => {
    const { rerender } = render(<StepIndicator {...defaultProps} step={1} />)

    let activeTab = screen.getByRole('tab', { name: /Анализ/ })
    expect(activeTab).toHaveAttribute('aria-selected', 'true')

    rerender(<StepIndicator {...defaultProps} step={2} selectedGame={mockGame} />)
    activeTab = screen.getByRole('tab', { name: /Тиражи/ })
    expect(activeTab).toHaveAttribute('aria-selected', 'true')

    // Non-active tabs should have aria-selected=false
    const tab1 = screen.getByRole('tab', { name: /Анализ/ })
    expect(tab1).toHaveAttribute('aria-selected', 'false')
  })

  it('tab 1 is always enabled', () => {
    render(<StepIndicator {...defaultProps} />)

    const tab1 = screen.getByRole('tab', { name: /Анализ/ })
    expect(tab1).not.toBeDisabled()
  })
})
