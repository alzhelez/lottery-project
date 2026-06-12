/**
 * Smoke test: adapters from @/lib/adapters
 *
 * Verifies both adapters handle realistic Python output shapes,
 * null/undefined nested values gracefully, and never throw even with
 * completely malformed input.
 */
import { describe, it, expect } from 'vitest'
import { adaptPredictResult, adaptPipelineResult } from '@/lib/adapters'
import type { PredictionResult, PipelineResult } from '@/components/lottery/types'

describe('adaptPredictResult with realistic Python output', () => {
  it('adapts a full predict output structure correctly', () => {
    const pythonOutput: Record<string, unknown> = {
      status: 'success',
      game: '4x20',
      game_format: {
        pick_b1: 4,
        pick_b2: 4,
        total_models: 133,
      },
      data_quality: {
        total_draws: 2500,
      },
      prediction: {
        block1: [3, 7, 12, 18],
        block2: [1, 5, 9, 14],
        consensus_agreement_b1: 0.85,
        consensus_agreement_b2: 0.72,
        consensus_votes_b1: { '3': 45, '7': 38, '12': 30, '18': 28 },
        consensus_votes_b2: { '1': 50, '5': 42, '9': 35, '14': 25 },
      },
      accuracy: {
        last_50_avg: 2.3,
        last_100_avg: 2.1,
        last_200_avg: 1.9,
        improvement_pct: 12.5,
        baseline_random: 1.6,
      },
      monte_carlo: {
        iterations: 10000,
        mean: 2.4,
        p5: 1.0,
        p95: 4.0,
        p_ge5: 0.15,
      },
      cross_validation: {
        mean_accuracy: 2.2,
        std_accuracy: 0.3,
        folds: 5,
      },
      backtest: {
        heatmap: [
          { draw_no: 100, hits: 2 },
          { draw_no: 101, hits: 3 },
        ],
      },
      analysis_methods: ['frequency', 'markov', 'mlp'],
      frequency_analysis: {
        block1: [{ number: 3, count: 150, last_seen: 5 }],
        block2: [{ number: 1, count: 200, last_seen: 2 }],
      },
      sum_range_stats: { block1: { min: 15, max: 45 } },
    }

    const result = adaptPredictResult(pythonOutput)

    expect(result).toBeDefined()
    expect(result.status).toBe('success')
    expect(result.game_key).toBe('4x20')
    expect(result.total_draws).toBe(2500)
    expect(result.prediction.block1).toEqual([3, 7, 12, 18])
    expect(result.prediction.block2).toEqual([1, 5, 9, 14])
    expect(result.monte_carlo.iterations).toBe(10000)
    expect(result.backtest.heatmap).toHaveLength(2)
    expect(result.consensusVotesB1).toEqual({ '3': 45, '7': 38, '12': 30, '18': 28 })
  })

  it('handles null/undefined nested values gracefully', () => {
    const sparseInput: Record<string, unknown> = {
      status: 'success',
      game: '5x36',
      prediction: {
        block1: null,
        block2: undefined,
      },
    }

    const result = adaptPredictResult(sparseInput)

    expect(result).toBeDefined()
    expect(result.status).toBe('success')
    expect(result.prediction.block1).toEqual([])
    expect(result.prediction.block2).toEqual([])
    expect(result.total_draws).toBe(0)
    expect(result.models_used).toBe(133) // fallback
  })

  it('handles completely empty/malformed input without throwing', () => {
    expect(() => adaptPredictResult({})).not.toThrow()
    expect(() => adaptPredictResult({ status: 'error' } as Record<string, unknown>)).not.toThrow()

    const result = adaptPredictResult({})
    expect(result).toBeDefined()
    expect(result.status).toBe('')
    expect(result.prediction.block1).toEqual([])
  })

  it('handles top5_models predictions', () => {
    const input: Record<string, unknown> = {
      status: 'ok',
      game_format: { pick_b1: 4, pick_b2: 4, total_models: 50 },
      data_quality: { total_draws: 100 },
      prediction: { block1: [1, 2, 3, 4], block2: [5, 6, 7, 8] },
      accuracy: {},
      top5_models: {
        predictions: [
          { name: 'model-a', score: 0.9, b1: [1, 2, 3, 4], b2: [5, 6, 7, 8] },
          { name: 'model-b', score: 0.8, b1: [2, 3, 4, 5], b2: [6, 7, 8, 9] },
        ],
      },
    }

    const result = adaptPredictResult(input)
    expect((result as Record<string, unknown>).top5_models).toBeDefined()
  })
})

describe('adaptPipelineResult with realistic Python output', () => {
  it('adapts a full pipeline output structure correctly', () => {
    const pythonOutput: Record<string, unknown> = {
      status: 'success',
      game: '4x20',
      pick_b1: 4,
      pick_b2: 4,
      accuracy_entries: 1800,
      confidence: {
        b1_score: 0.82,
        b2_score: 0.71,
        overall: 0.77,
        consensus_strength: 0.65,
      },
      position_details: {
        b1: { pos_1: { selected: 3, votes: { '3': 25 } } },
        b2: { pos_1: { selected: 7, votes: { '7': 30 } } },
      },
      final_prediction: {
        block1: [3, 7, 12, 18],
        block2: [2, 9, 14, 17],
      },
      block1_position: {
        prediction: [3, 7, 12, 18],
        confidence: 0.85,
        details: { pos_1: { selected: 3, votes: { '3': 40 } } },
      },
      block1_frequency: {
        prediction: [3, 7, 12, 18],
        details: [{ number: 3, count: 200, last_seen: 1, recency_score: 0.95 }],
      },
      top3_models: {
        models: [{ id: 1, name: 'mlp_v1', avg_hits: 2.5, b1: [3, 7, 12, 18], b2: [2, 9, 14, 17] }],
      },
      number_spectrum: {
        block1: [{ number: 3, votes: 45 }],
        block2: [{ number: 2, votes: 38 }],
      },
    }

    const result = adaptPipelineResult(pythonOutput, '4x20')

    expect(result).toBeDefined()
    expect(result.status).toBe('success')
    expect(result.game_key).toBe('4x20')
    expect(result.total_draws).toBe(1800)
    expect(result.prediction.block1).toEqual([3, 7, 12, 18])
    expect(result.prediction.block2).toEqual([2, 9, 14, 17])
    expect(result.confidence.overall).toBe(0.77)
    expect(result.block1_position?.confidence).toBe(0.85)
    expect(result.top3_models?.models).toHaveLength(1)
    expect(result.number_spectrum?.block1).toHaveLength(1)
  })

  it('handles null/undefined nested values gracefully', () => {
    const sparseInput: Record<string, unknown> = {
      status: 'success',
    }

    const result = adaptPipelineResult(sparseInput, 'keno2')

    expect(result).toBeDefined()
    expect(result.game_key).toBe('keno2')
    expect(result.prediction.block1).toEqual([])
    expect(result.prediction.block2).toEqual([])
    expect(result.confidence.block1).toBe(0)
    expect(result.confidence.block2).toBe(0)
  })

  it('handles completely empty/malformed input without throwing', () => {
    expect(() => adaptPipelineResult({} as Record<string, unknown>, 'test')).not.toThrow()
    expect(() => adaptPipelineResult({ status: 'error' } as Record<string, unknown>, 'test')).not.toThrow()

    const result = adaptPipelineResult({}, 'fallback-key')
    expect(result).toBeDefined()
    expect(result.game_key).toBe('fallback-key')
    expect(result.status).toBe('')
  })

  it('never throws on any object input shape', () => {
    const weirdInputs = [
      {},
      { status: 123 },
      { prediction: 'not-an-object' },
      { confidence: 'bad' },
    ]
    for (const input of weirdInputs) {
      expect(() => adaptPipelineResult(input as Record<string, unknown>, 'x')).not.toThrow()
    }
  })
})
