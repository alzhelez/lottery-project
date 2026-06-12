import { describe, it, expect } from 'vitest'
import { adaptPredictResult, adaptPipelineResult } from '@/lib/adapters'

describe('adaptPredictResult', () => {
  it('maps full data with all fields to correct typed output', () => {
    const raw: Record<string, unknown> = {
      status: 'ok',
      game: '4x20',
      game_format: { pick_b1: 4, pick_b2: 4 },
      total_models: 133,
      data_quality: { total_draws: 1500 },
      prediction: {
        block1: [3, 7, 12, 19],
        block2: [5, 11, 14, 20],
        consensus_agreement_b1: 0.65,
        consensus_agreement_b2: 0.42,
        consensus_votes_b1: { '3': 80, '7': 75 },
        consensus_votes_b2: { '5': 60 },
      },
      accuracy: {
        last_50_avg: 1.4,
        last_100_avg: 1.3,
        last_200_avg: 1.2,
        improvement_pct: 12.5,
        baseline_random: 0.8,
      },
      monte_carlo: {
        mean: 1.35,
        p5: 0.5,
        p95: 2.1,
        p_ge5: 0.08,
        iterations: 10000,
      },
      cross_validation: { score: 0.72 },
      backtest: {
        heatmap: [{ draw_no: 1, pred_b1: [3, 7], act_b1: [3, 7], hits_b1: 2 }],
      },
      analysis_methods: ['frequency', 'entropy'],
      top5_models: {
        predictions: [
          { model_id: 1, name: 'model1', b1: [3, 7, 12, 19], b2: [5, 11, 14, 20], score: 1.5 },
          { model_id: 2, name: 'model2', b1: [1, 5, 12, 19], b2: [3, 11, 14, 20], score: 1.3 },
        ],
      },
    }

    const result = adaptPredictResult(raw)

    expect(result.status).toBe('ok')
    expect(result.game_key).toBe('4x20')
    expect(result.game_format).toBe('4×4')
    expect(result.total_draws).toBe(1500)
    expect(result.prediction.block1).toEqual([3, 7, 12, 19])
    expect(result.prediction.block2).toEqual([5, 11, 14, 20])
    expect(result.consensus_strength.block1).toBe(0.65)
    expect(result.consensus_strength.block2).toBe(0.42)
    expect(result.random_baseline.expected_hits).toBe(0.8)
    expect(result.models_used).toBe(133)
    expect(result.analysis_methods).toEqual(['frequency', 'entropy'])
  })

  it('handles minimal data (empty object) without crashing and uses fallback defaults', () => {
    const result = adaptPredictResult({})

    expect(result.status).toBe('')
    expect(result.game_format).toBe('?×?')
    expect(result.total_draws).toBe(0)
    expect(result.prediction.block1).toEqual([])
    expect(result.prediction.block2).toEqual([])
    expect(result.consensus_strength.block1).toBe(0)
    expect(result.consensus_strength.block2).toBe(0)
    expect(result.models_used).toBe(133) // default
    expect(result.analysis_methods).toEqual([])
    expect(result.monte_carlo).toEqual({})
    expect(result.cross_validation).toEqual({})
    expect(result.backtest).toEqual({})
  })

  it('maps prediction block1 and block2 arrays correctly', () => {
    const raw: Record<string, unknown> = {
      prediction: {
        block1: [1, 2, 3],
        block2: [10, 20],
      },
    }

    const result = adaptPredictResult(raw)
    expect(result.prediction.block1).toEqual([1, 2, 3])
    expect(result.prediction.block2).toEqual([10, 20])
  })

  it('populates consensusVotesB1/B2 when consensus votes are present', () => {
    const raw: Record<string, unknown> = {
      prediction: {
        consensus_votes_b1: { '3': 80, '7': 75 },
        consensus_votes_b2: { '5': 60 },
      },
    }

    const result = adaptPredictResult(raw)
    expect(result.consensusVotesB1).toEqual({ '3': 80, '7': 75 })
    expect(result.consensusVotesB2).toEqual({ '5': 60 })
  })

  it('adds top5_models and maps predictions to prediction keys', () => {
    const raw: Record<string, unknown> = {
      top5_models: {
        predictions: [
          { model_id: 1, name: 'm1', b1: [1], b2: [2], score: 1.5 },
          { model_id: 2, name: 'm2', b1: [3], b2: [4], score: 1.3 },
        ],
      },
    }

    const result = adaptPredictResult(raw)
    expect((result as Record<string, unknown>).top5_models).toBeDefined()
    expect((result.prediction as Record<string, unknown>).top_model_1).toEqual({
      model_id: 1, name: 'm1', b1: [1], b2: [2], score: 1.5,
    })
    expect((result.prediction as Record<string, unknown>).top_model_2).toEqual({
      model_id: 2, name: 'm2', b1: [3], b2: [4], score: 1.3,
    })
  })

  it('populates monte_carlo result with iterations, expected_hits, ci bounds, p_ge_5', () => {
    const raw: Record<string, unknown> = {
      monte_carlo: {
        mean: 1.35,
        p5: 0.5,
        p95: 2.1,
        p_ge5: 0.08,
        iterations: 10000,
      },
    }

    const result = adaptPredictResult(raw)
    expect(result.monte_carlo).toEqual({
      iterations: 10000,
      expected_hits: 1.35,
      ci_95_low: 0.5,
      ci_95_high: 2.1,
      p_ge_5: 0.08,
    })
  })
})

describe('adaptPipelineResult', () => {
  it('maps full data with game_key, confidence.overall, and prediction', () => {
    const raw: Record<string, unknown> = {
      status: 'ok',
      game: '4x20',
      pick_b1: 4,
      pick_b2: 4,
      accuracy_entries: 1500,
      confidence: {
        b1_score: 0.72,
        b2_score: 0.65,
        overall: 0.68,
        consensus_strength: 0.55,
      },
      final_prediction: {
        block1: [3, 7, 12, 19],
        block2: [5, 11, 14, 20],
      },
      position_details: {
        b1: { '1': { selected: 3, votes: { '3': 50 } } },
        b2: {},
      },
    }

    const result = adaptPipelineResult(raw, 'fallback')

    expect(result.status).toBe('ok')
    expect(result.game_key).toBe('4x20')
    expect(result.game_format).toBe('4×4')
    expect(result.total_draws).toBe(1500)
    expect(result.runs_performed).toBe(1)
    expect(result.prediction.block1).toEqual([3, 7, 12, 19])
    expect(result.prediction.block2).toEqual([5, 11, 14, 20])
    expect(result.confidence.block1).toBe(0.72)
    expect(result.confidence.block2).toBe(0.65)
    expect(result.confidence.overall).toBe(0.68)
    expect(result.confidence.consensus_strength).toBe(0.55)
  })

  it('uses fallbackGameKey when raw.game is empty', () => {
    const raw: Record<string, unknown> = { game: '' }
    const result = adaptPipelineResult(raw, '4x20')
    expect(result.game_key).toBe('4x20')
  })

  it('handles empty raw {} without crashing, provides fallback values', () => {
    const result = adaptPipelineResult({}, 'fallback-key')

    expect(result.status).toBe('')
    expect(result.game_key).toBe('fallback-key')
    expect(result.game_format).toBe('?×?')
    expect(result.total_draws).toBe(0)
    expect(result.runs_performed).toBe(1)
    expect(result.prediction.block1).toEqual([])
    expect(result.prediction.block2).toEqual([])
    expect(result.confidence.block1).toBe(0)
    expect(result.confidence.block2).toBe(0)
    expect(result.confidence.overall).toBe(0)
    expect(result.individual_predictions).toEqual([])
    expect(result.position_analysis.block1).toEqual({})
    expect(result.position_analysis.block2).toEqual({})
  })

  it('includes number_spectrum when present in raw data', () => {
    const spectrum = {
      block1: [{ number: 3, votes: 80 }, { number: 7, votes: 75 }],
      block2: [{ number: 5, votes: 60 }],
    }
    const raw: Record<string, unknown> = { number_spectrum: spectrum }

    const result = adaptPipelineResult(raw, '4x20')
    expect(result.number_spectrum).toEqual(spectrum)
  })

  it('includes top3_models when present in raw data', () => {
    const top3 = {
      models: [
        { id: 1, name: 'm1', avg_hits: 1.5, b1: [3, 7], b2: [5] },
        { id: 2, name: 'm2', avg_hits: 1.3, b1: [1, 5], b2: [3] },
      ],
    }
    const raw: Record<string, unknown> = { top3_models: top3 }

    const result = adaptPipelineResult(raw, '4x20')
    expect(result.top3_models).toEqual(top3)
  })
})
