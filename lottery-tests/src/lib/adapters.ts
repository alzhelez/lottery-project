/**
 * Type-safe adapters for converting raw Python API responses
 * into strongly-typed frontend objects.
 *
 * All functions accept `Record<string, unknown>` (raw JSON from Python)
 * and return properly typed objects defined in `@/components/lottery/types`.
 */

import type { PredictionResult, PipelineResult } from '@/components/lottery/types'

// ── Helpers ────────────────────────────────────────────────────────────────

/** Safely read a nested key chain from a raw object. */
function dig(obj: Record<string, unknown>, ...keys: string[]): unknown {
  let current: unknown = obj
  for (const key of keys) {
    if (current == null || typeof current !== 'object') return undefined
    current = (current as Record<string, unknown>)[key]
  }
  return current
}

function num(obj: Record<string, unknown>, key: string, fallback = 0): number {
  const v = obj[key]
  return typeof v === 'number' ? v : fallback
}

function str(obj: Record<string, unknown>, key: string, fallback = ''): string {
  const v = obj[key]
  return typeof v === 'string' ? v : fallback
}

function arr<T = unknown>(obj: Record<string, unknown>, key: string): T[] {
  const v = obj[key]
  return Array.isArray(v) ? v as T[] : []
}

function rec(obj: Record<string, unknown>, key: string): Record<string, unknown> {
  const v = obj[key]
  return v != null && typeof v === 'object' && !Array.isArray(v)
    ? v as Record<string, unknown>
    : {}
}

// ── Predict Adapter ───────────────────────────────────────────────────────

export function adaptPredictResult(raw: Record<string, unknown>): PredictionResult {
  const acc = rec(raw, 'accuracy')
  const mc = rec(raw, 'monte_carlo')
  const cv = raw.cross_validation
  const backtest = rec(raw, 'backtest')
  const top5 = rec(raw, 'top5_models')
  const prediction = rec(raw, 'prediction')
  const votesB1 = dig(raw, 'prediction', 'consensus_votes_b1') as Record<string, number> | undefined
  const votesB2 = dig(raw, 'prediction', 'consensus_votes_b2') as Record<string, number> | undefined
  const gameFormat = rec(raw, 'game_format')
  const dataQuality = rec(raw, 'data_quality')

  // ── Backtest ──────────────────────────────────────────────────────────
  const hasHeatmap = 'heatmap' in backtest
  const hasAvgStats = 'last_50_avg' in backtest

  const backtestResult: Record<string, unknown> = hasHeatmap
    ? {
        last_50_avg: num(acc, 'last_50_avg'),
        last_100_avg: num(acc, 'last_100_avg'),
        last_200_avg: num(acc, 'last_200_avg'),
        improvement_pct: num(acc, 'improvement_pct'),
        baseline_random: num(acc, 'baseline_random'),
        heatmap: backtest.heatmap,
      }
    : hasAvgStats
      ? {
          last_50_avg: num(acc, 'last_50_avg'),
          last_100_avg: num(acc, 'last_100_avg'),
          last_200_avg: num(acc, 'last_200_avg'),
          improvement_pct: num(acc, 'improvement_pct'),
          baseline_random: num(acc, 'baseline_random'),
        }
      : {}

  // ── Monte Carlo ──────────────────────────────────────────────────────
  const mcResult: Record<string, unknown> = {}
  if (mc && typeof mc === 'object' && 'mean' in mc) {
    mcResult.iterations = (mc as Record<string, number>).iterations || 5000
    mcResult.expected_hits = (mc as Record<string, number>).mean
    mcResult.ci_95_low = (mc as Record<string, number>).p5
    mcResult.ci_95_high = (mc as Record<string, number>).p95
    mcResult.p_ge_5 = (mc as Record<string, number>).p_ge5
  }

  // ── Cross Validation ─────────────────────────────────────────────────
  const cvResult: Record<string, unknown> = {}
  if (cv && typeof cv === 'object' && !(cv as Record<string, unknown>).error) {
    Object.assign(cvResult, cv)
  }

  // ── Assemble ─────────────────────────────────────────────────────────
  const data: PredictionResult = {
    status: str(raw, 'status'),
    game_format: `${dig(gameFormat, 'pick_b1') ?? '?'}×${dig(gameFormat, 'pick_b2') ?? '?'}`,
    game_key: str(raw, 'game'),
    total_draws: num(dataQuality, 'total_draws'),
    prediction: {
      block1: Array.isArray(prediction.block1) ? prediction.block1 as number[] : [],
      block2: Array.isArray(prediction.block2) ? prediction.block2 as number[] : [],
      block1_methods: [],
      block2_methods: [],
    },
    consensus_strength: {
      block1: (prediction.consensus_agreement_b1 as number) ?? 0,
      block2: (prediction.consensus_agreement_b2 as number) ?? 0,
    },
    random_baseline: {
      block1: [],
      block2: [],
      expected_hits: num(acc, 'baseline_random'),
    },
    cross_validation: cvResult,
    backtest: backtestResult,
    monte_carlo: mcResult,
    models_used: num(gameFormat, 'total_models', 133),
    analysis_methods: Array.isArray(raw.analysis_methods) ? raw.analysis_methods as string[] : [],
    sum_range_stats: (raw.sum_range_stats as Record<string, unknown>) ?? null,
    cross_game: (raw.cross_game_analysis as Record<string, unknown>) ?? null,
    draw_schedule: raw.draw_schedule as Record<string, unknown> | undefined,
    frequency_analysis: raw.frequency_analysis as PredictionResult['frequency_analysis'] | undefined,
    pair_analysis: raw.pair_analysis as PredictionResult['pair_analysis'] | undefined,
    gap_analysis: raw.gap_analysis as PredictionResult['gap_analysis'] | undefined,
    // v39.0.0: New analysis fields from P0/P1/P2 improvements
    transition_pagerank: raw.transition_pagerank as Record<string, unknown> | undefined,
    second_order_markov: raw.second_order_markov as Record<string, unknown> | undefined,
    autocorrelation: raw.autocorrelation as Record<string, unknown> | undefined,
    regime_detection: raw.regime_detection as Record<string, unknown> | undefined,
    day_of_week: raw.day_of_week as Record<string, unknown> | undefined,
    autoregressive_trend: raw.autoregressive_trend as Record<string, unknown> | undefined,
    meta_learner: raw.meta_learner as Record<string, unknown> | undefined,
    // v39.1.0: Meta-learner flag
    _meta_learner_used: raw.prediction?._meta_learner_used as boolean | undefined,
    // v39.4.0: Prediction info (data used + next draw number)
    predictionInfo: raw.prediction_info as PredictionResult['predictionInfo'] | undefined,
  }

  // ── Top-5 model predictions ──────────────────────────────────────────
  if (top5.predictions && Array.isArray(top5.predictions)) {
    ;(data as Record<string, unknown>).top5_models = top5
    ;(top5.predictions as unknown[]).forEach((pred: unknown, idx: number) => {
      const key = `top_model_${idx + 1}` as keyof typeof data.prediction
      ;(data.prediction as Record<string, unknown>)[key] = pred
    })
  }

  // ── Consensus votes ──────────────────────────────────────────────────
  if (votesB1 && Object.keys(votesB1).length > 0) {
    data.consensusVotesB1 = votesB1
  }
  if (votesB2 && Object.keys(votesB2).length > 0) {
    data.consensusVotesB2 = votesB2
  }

  return data
}

// ── Pipeline Adapter ──────────────────────────────────────────────────────

export function adaptPipelineResult(
  raw: Record<string, unknown>,
  fallbackGameKey: string,
): PipelineResult {
  const confidence = rec(raw, 'confidence')
  const positionDetails = rec(raw, 'position_details')
  const finalPrediction = rec(raw, 'final_prediction')

  return {
    status: str(raw, 'status'),
    game_key: str(raw, 'game') || fallbackGameKey,
    game_format: `${raw.pick_b1 ?? '?'}×${raw.pick_b2 ?? '?'}`,
    total_draws: num(rec(raw, 'data_quality'), 'total_draws', num(raw, 'accuracy_entries')),
    runs_performed: 1,
    prediction: {
      block1: Array.isArray(finalPrediction.block1) ? finalPrediction.block1 as number[] : [],
      block2: Array.isArray(finalPrediction.block2) ? finalPrediction.block2 as number[] : [],
    },
    confidence: {
      block1: num(confidence, 'b1_score'),
      block2: num(confidence, 'b2_score'),
      overall: num(confidence, 'overall'),
      consensus_strength: num(confidence, 'consensus_strength'),
    },
    position_analysis: {
      block1: (positionDetails.b1 as Record<string, Record<string, unknown>>) ?? {},
      block2: (positionDetails.b2 as Record<string, Record<string, unknown>>) ?? {},
    },
    individual_predictions: [],
    block1_position: raw.block1_position as PipelineResult['block1_position'] ?? undefined,
    block1_frequency: raw.block1_frequency as PipelineResult['block1_frequency'] ?? undefined,
    block2_position: raw.block2_position as PipelineResult['block2_position'] ?? undefined,
    block2_frequency: raw.block2_frequency as PipelineResult['block2_frequency'] ?? undefined,
    top3_models: raw.top3_models as PipelineResult['top3_models'] ?? undefined,
    number_spectrum: raw.number_spectrum as PipelineResult['number_spectrum'] ?? undefined,
  }
}
