import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { HeatmapRow } from '@/components/lottery/HeatmapRow'
import type { HeatmapEntry } from '@/components/lottery/types'

vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <span data-testid="badge" className={className}>{children}</span>
  ),
}))

vi.mock('lucide-react', () => ({
  ChevronRight: ({ className }: { className?: string }) => (
    <svg data-testid="chevron" className={className} />
  ),
}))

const baseEntry: HeatmapEntry = {
  draw_no: 42,
  pred_b1: [1, 2, 3, 4],
  pred_b2: [5, 6, 7, 8],
  act_b1: [2, 4, 6, 8],
  act_b2: [5, 7, 9, 10],
  hits_b1: 2,
  hits_b2: 2,
  total: 4,
  date: '2025-01-15',
}

describe('HeatmapRow', () => {
  it('renders draw_no and date', () => {
    render(<HeatmapRow entry={baseEntry} bgColor="bg-blue-500/20" />)

    expect(screen.getByText('#42')).toBeInTheDocument()
    expect(screen.getByText('2025-01-15')).toBeInTheDocument()
  })

  it('expand/collapse — click toggles expanded state, shows "Блок 1 — Предсказание" when expanded', async () => {
    const user = userEvent.setup()
    render(<HeatmapRow entry={baseEntry} bgColor="bg-blue-500/20" />)

    // Initially collapsed
    expect(screen.queryByText('Блок 1 — Предсказание:')).not.toBeInTheDocument()

    // Click to expand
    await user.click(screen.getByRole('button'))
    expect(screen.getByText('Блок 1 — Предсказание:')).toBeInTheDocument()
    expect(screen.getByText('Блок 1 — Реальный:')).toBeInTheDocument()

    // Click to collapse
    await user.click(screen.getByRole('button'))
    expect(screen.queryByText('Блок 1 — Предсказание:')).not.toBeInTheDocument()
  })

  it('aria-expanded attribute toggles', async () => {
    const user = userEvent.setup()
    render(<HeatmapRow entry={baseEntry} bgColor="bg-blue-500/20" />)

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-expanded', 'false')

    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')

    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'false')
  })

  it('hit highlighting — numbers in pred_b1 that are also in act_b1 get emerald class', () => {
    render(<HeatmapRow entry={baseEntry} bgColor="bg-blue-500/20" />)

    // pred_b1 = [1,2,3,4], act_b1 = [2,4,6,8]
    // Numbers 2 and 4 are hits, 6 and 8 are non-hits
    const emeraldElements = screen.getAllByText(/2|4/, { selector: '.bg-emerald-500\\/40' })
    // We should find at least 2 and 4 highlighted — they appear both as numbers
    // Check that the highlighted spans contain our hit numbers
    const highlightedTexts = emeraldElements.map(el => el.textContent)
    expect(highlightedTexts).toContain('2')
    expect(highlightedTexts).toContain('4')

    // Non-hit numbers (6, 8) should not have emerald class
    const nonHit6 = screen.getByText('6', { selector: '.bg-white\\/5' })
    expect(nonHit6).toBeInTheDocument()
  })

  it('null-safe — act_b1=null, act_b2=null, pred_b1=[] — no crash', () => {
    const nullEntry: HeatmapEntry = {
      draw_no: 1,
      pred_b1: [],
      pred_b2: [],
      act_b1: null as unknown as number[],
      act_b2: null as unknown as number[],
      hits_b1: 0,
      hits_b2: 0,
      total: 0,
      date: '',
    }

    expect(() => {
      render(<HeatmapRow entry={nullEntry} bgColor="bg-red-500/20" />)
    }).not.toThrow()

    expect(screen.getByText('#1')).toBeInTheDocument()
  })

  it('bestModel prop — shows model name when expanded', async () => {
    const user = userEvent.setup()
    const bestModel = { name: 'XGBoost-v3', hits: 3 }

    render(
      <HeatmapRow
        entry={baseEntry}
        bgColor="bg-blue-500/20"
        bestModel={bestModel}
      />
    )

    // Not visible when collapsed
    expect(screen.queryByText('XGBoost-v3')).not.toBeInTheDocument()

    // Expand
    await user.click(screen.getByRole('button'))

    expect(screen.getByText('XGBoost-v3')).toBeInTheDocument()
    expect(screen.getByText('(3 попад.)')).toBeInTheDocument()
  })
})
