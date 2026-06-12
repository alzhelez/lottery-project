import { Dice1, Dice2, Dice3, Dice4, Dice5 } from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────────────────

export interface GameAnalysis {
  name: string
  key?: string
  score: number
  verdict: string
  verdict_color: string
  draws: number
  hot_numbers: number[]
  cold_numbers: number[]
  chi2_p: number | null
  autocorr: number | null
  data_file?: string
  source?: string
  has_local_data?: boolean
  redirect_target?: string | null
}

export interface GameCategories {
  high: GameAnalysis[]
  moderate: GameAnalysis[]
  normal: GameAnalysis[]
  insufficient: GameAnalysis[]
}

export interface PredictionResult {
  status: string
  game_format: string
  game_key?: string
  total_draws: number
  prediction: {
    block1: number[]
    block2: number[]
    block1_methods?: number[][]
    block2_methods?: number[][]
    top_model_1?: { name: string; score: number; b1: number[]; b2: number[] }
    top_model_2?: { name: string; score: number; b1: number[]; b2: number[] }
    top_model_3?: { name: string; score: number; b1: number[]; b2: number[] }
    top_model_4?: { name: string; score: number; b1: number[]; b2: number[] }
    top_model_5?: { name: string; score: number; b1: number[]; b2: number[] }
    [key: string]: unknown
  }
  consensus_strength: {
    block1: number
    block2: number
  }
  random_baseline: {
    block1: number[]
    block2: number[]
    expected_hits: number
  }
  cross_validation: Record<string, unknown>
  backtest: Record<string, unknown>
  monte_carlo: Record<string, unknown>
  models_used: number
  analysis_methods: string[]
  error?: string
  draw_schedule?: Record<string, unknown>
  frequency_analysis?: { block1: { number: number; count: number; last_seen: number }[]; block2: { number: number; count: number; last_seen: number }[] }
  pair_analysis?: { pairs: { pair: number[]; count: number; last_seen: number }[]; total_draws: number }
  gap_analysis?: { block1: { number: number; gap: number; avg_gap: number | null; frequency: number; overdue_score: number }[]; block2: { number: number; gap: number; avg_gap: number | null; frequency: number; overdue_score: number }[] }
  sum_range_stats?: Record<string, Record<string, unknown>>
  cross_game?: Record<string, unknown>
  transition_pagerank?: Record<string, unknown>
  second_order_markov?: Record<string, unknown>
  autocorrelation?: Record<string, unknown>
  regime_detection?: Record<string, unknown>
  meta_learner?: Record<string, unknown>
  day_of_week?: Record<string, unknown>
  autoregressive_trend?: Record<string, unknown>
  consensusVotesB1?: Record<string, number>
  consensusVotesB2?: Record<string, number>
  predictionInfo?: {
    total_draws_used: number
    draw_range: string | null
    last_draw_no: number | null
    next_draw_no: number | null
    game_key: string
  }
  [key: string]: unknown
}

export interface HeatmapEntry {
  draw_no: number
  pred_b1: number[]
  pred_b2: number[]
  act_b1: number[]
  act_b2: number[]
  hits_b1: number
  hits_b2: number
  total: number
  date: string
}

export interface Top5ModelRanking {
  model_id: number
  name: string
  score: number
  avg_hits: number
  b1_avg: number
  b2_avg: number
  draws_tested: number
}

export interface Top5ModelPrediction {
  model_id: number
  name: string
  b1: number[]
  b2: number[]
  score: number
}

export interface PipelineResult {
  status: string
  game_key: string
  game_format: string
  total_draws: number
  runs_performed: number
  prediction: {
    block1: number[]
    block2: number[]
  }
  confidence: {
    block1: number
    block2: number
    overall: number
    consensus_strength?: number
  }
  position_analysis: {
    block1: Record<string, Record<string, unknown>>
    block2: Record<string, Record<string, unknown>>
  }
  individual_predictions: { block1: number[]; block2: number[] }[]
  block1_position?: {
    prediction: number[]
    confidence: number
    details: Record<string, { selected: number; votes: Record<string, number> }>
  }
  block1_frequency?: {
    prediction: number[]
    details: { number: number; count: number; last_seen: number; recency_score: number }[]
  }
  block2_position?: {
    prediction: number[]
    confidence: number
    details: Record<string, { selected: number; votes: Record<string, number> }>
  }
  block2_frequency?: {
    prediction: number[]
    details: { number: number; count: number; last_seen: number; recency_score: number }[]
  }
  top3_models?: {
    models: { id: number; name: string; avg_hits: number; b1: number[]; b2: number[] }[]
  }
  number_spectrum?: {
    block1: { number: number; votes: number }[]
    block2: { number: number; votes: number }[]
  }
  error?: string
}

export interface GodModeResult {
  status: string
  runs_total: number
  runs_failed: number
  frequency_b1: Record<string, number>
  frequency_b2: Record<string, number>
  top_numbers_b1: Array<{ number: string; count: number }>
  top_numbers_b2: Array<{ number: string; count: number }>
  /** v38.1: backtest-weighted top numbers */
  top_numbers_b1_weighted?: Array<{ number: string; score: number }>
  top_numbers_b2_weighted?: Array<{ number: string; score: number }>
  /** v38.2: Rank-weighted top numbers */
  top_numbers_b1_ranked?: Array<{ number: string; score: number }>
  top_numbers_b2_ranked?: Array<{ number: string; score: number }>
  /** v38.2: Meta-consensus — numbers backed by ≥3 strategies */
  meta_consensus_b1?: Array<{ number: string; strategyCount: number; strategies: string[] }>
  meta_consensus_b2?: Array<{ number: string; strategyCount: number; strategies: string[] }>
  /** v38.2: Confidence 0-100 per number */
  confidence_b1?: Array<{ number: string; confidence: number }>
  confidence_b2?: Array<{ number: string; confidence: number }>
  consensus_distribution: Array<{ block1: number; block2: number; avg: number }>
  avg_consensus_b1: number
  avg_consensus_b2: number
  best_run: {
    params: Record<string, unknown>
    consensus_strength: { block1: number; block2: number }
    prediction: { block1: number[]; block2: number[] }
    accuracy?: { last_50_avg: number; baseline_random: number; improvement_pct: number | null }
  }
  worst_run: {
    params: Record<string, unknown>
    consensus_strength: { block1: number; block2: number }
    prediction: { block1: number[]; block2: number[] }
    accuracy?: { last_50_avg: number; baseline_random: number; improvement_pct: number | null }
  }
  /** v38.1: Best run by backtest accuracy */
  best_accuracy_run?: {
    params: Record<string, unknown>
    consensus_strength: { block1: number; block2: number }
    prediction: { block1: number[]; block2: number[] }
    accuracy?: { last_50_avg: number; baseline_random: number; improvement_pct: number | null }
  } | null
  strategy_stats?: Array<{
    strategy: string
    count: number
    avg_consensus_b1: number
    avg_consensus_b2: number
    avg_accuracy: number
    avg_improvement: number
  }>
  individual_runs: {
    params: Record<string, unknown>
    prediction: { block1: number[]; block2: number[] }
    consensus_strength: { block1: number; block2: number }
    backtest: Record<string, unknown> | null
    accuracy?: { last_50_avg: number; baseline_random: number; improvement_pct: number | null }
    error?: string
  }[]
  game_format: string
  total_draws: number
  predictionInfo?: {
    total_draws_used: number
    draw_range: string | null
    last_draw_no: number | null
    next_draw_no: number | null
    game_key: string
  }
}

export type WizardStep = 1 | 2 | 3 | 4 | 5

// ── Constants ────────────────────────────────────────────────────────────────

export const GAME_ICONS: Record<string, typeof Dice1> = {
  '4x20': Dice1,
  '6x45plus': Dice2,
  '5x36plus': Dice3,
  '5x2': Dice4,
  'keno2': Dice5,
}

export const GAME_FORMATS: Record<string, { blocks: string; pick_b1: number; pick_b2: number; b1_range: string; b2_range: string; example: string }> = {
  // ── Known two-block games ──
  '4x20': { blocks: '2 блока', pick_b1: 4, pick_b2: 4, b1_range: '1-20', b2_range: '1-20', example: '11.04.2026 23:22||13280||20,7,13,1||18,17,14,9' },
  '6x45plus': { blocks: '2 блока', pick_b1: 6, pick_b2: 1, b1_range: '1-45', b2_range: '1-4', example: '11.04.2026 23:30||186||45,33,11,12,18,6||2' },
  '5x36plus': { blocks: '2 блока', pick_b1: 5, pick_b2: 1, b1_range: '1-36', b2_range: '1-4', example: '11.04.2026 23:30||157228||28,33,22,8,3||1' },
  '5x2': { blocks: '2 блока', pick_b1: 5, pick_b2: 2, b1_range: '1-50', b2_range: '1-10', example: '10.04.2026 21:30||1892||7,14,22,35,48||3,11' },
  'keno2': { blocks: '2 блока', pick_b1: 20, pick_b2: 1, b1_range: '1-80', b2_range: '1-10', example: '11.04.2026 23:17||320331||2,9,7,8,8,0,3,1,1,19,1,30,55,23,61,34,13,29,46,56||5' },
  'rapido': { blocks: '2 блока', pick_b1: 8, pick_b2: 1, b1_range: '1-20', b2_range: '1-4', example: '11.04.2026 20:00||54321||3,7,12,15,1,8,19,4||2' },
  '6x49plus': { blocks: '2 блока', pick_b1: 6, pick_b2: 1, b1_range: '1-49', b2_range: '1-4', example: '11.04.2026 21:00||7890||12,5,34,22,47,8||3' },
  '4x20plus': { blocks: '2 блока', pick_b1: 4, pick_b2: 1, b1_range: '1-20', b2_range: '1-4', example: '11.04.2026 19:00||4567||5,12,17,3||1' },
  '5x2_2': { blocks: '2 блока', pick_b1: 5, pick_b2: 2, b1_range: '1-50', b2_range: '1-10', example: '10.04.2026 22:00||987||14,28,37,5,41||2,8' },
  'djoker': { blocks: '2 блока', pick_b1: 5, pick_b2: 1, b1_range: '1-36', b2_range: '1-6', example: '11.04.2026 18:00||3210||7,15,22,33,4||2' },

  // ── Known single-block games ──
  '7x49': { blocks: '1 блок', pick_b1: 7, pick_b2: 0, b1_range: '1-49', b2_range: '-', example: '11.04.2026 21:00||4567||12,5,34,22,47,8,19||' },
  '6x45': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-45', b2_range: '-', example: '11.04.2026 23:30||186||45,33,11,12,18,6||' },
  '5x36': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 23:30||157228||28,33,22,8,3||' },
  'top3': { blocks: '1 блок', pick_b1: 3, pick_b2: 0, b1_range: '1-9', b2_range: '-', example: '11.04.2026 20:00||9999||3,7,1||' },
  'zabeg': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-20', b2_range: '-', example: '11.04.2026 19:00||1234||5,12,17,3,9,14||' },
  'zabegalochka': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-20', b2_range: '-', example: '11.04.2026 18:00||5678||2,8,15,11,19,4||' },
  'duel': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-20', b2_range: '-', example: '11.04.2026 17:00||9012||7,3,14,18,6,11||' },
  '12x24': { blocks: '1 блок', pick_b1: 12, pick_b2: 0, b1_range: '1-24', b2_range: '-', example: '11.04.2026 21:00||3456||1,3,5,7,9,11,13,15,17,19,21,23||' },
  '6x36': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 22:00||6789||4,12,28,33,7,19||' },
  'sportloto': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-49', b2_range: '-', example: '11.04.2026 20:00||1111||3,17,29,42,8,35||' },
  '5x36lite': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 19:30||2222||6,14,23,31,9||' },
  'kvartet': { blocks: '1 блок', pick_b1: 4, pick_b2: 0, b1_range: '1-20', b2_range: '-', example: '11.04.2026 16:00||3333||5,11,17,3||' },
  'bingo75': { blocks: '1 блок', pick_b1: 15, pick_b2: 0, b1_range: '1-75', b2_range: '-', example: '11.04.2026 15:00||4444||2,7,12,18,23,28,33,38,43,48,53,58,63,68,71||' },
  'bingo': { blocks: '1 блок', pick_b1: 15, pick_b2: 0, b1_range: '1-75', b2_range: '-', example: '11.04.2026 14:00||5555||1,6,15,22,29,36,41,48,55,60,65,70,73,74,75||' },

  // ── Unknown / special games (generic format) ──
  'moment': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 12:00||6666||8,14,22,31,5||' },
  'xoroshist': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 11:00||7777||3,9,17,24,35||' },
  'rk': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 10:00||8888||2,11,19,27,33||' },
  'goldenkey': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 09:00||9999||4,12,21,30,7||' },
  'nards-pro': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 08:00||1011||5,11,18,26,33,9||' },
  'gzhl': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-45', b2_range: '-', example: '11.04.2026 07:00||1213||7,14,23,31,38,5||' },
  'football-gold': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 06:00||1415||1,8,16,25,34||' },
  'dvazhdydva': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-49', b2_range: '-', example: '11.04.2026 05:00||1617||3,10,22,35,41,48||' },
  'prize': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 04:00||1819||6,13,20,28,34||' },
  'goldenkhanka': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 03:00||2021||2,9,17,25,32||' },
  'expres': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-49', b2_range: '-', example: '11.04.2026 02:00||2223||4,11,19,27,36,44||' },
  'ruslotto': { blocks: '1 блок', pick_b1: 6, pick_b2: 0, b1_range: '1-45', b2_range: '-', example: '11.04.2026 01:00||2425||8,15,22,31,39,3||' },
  'architect': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 00:00||2627||1,10,18,27,35||' },
  'syndicate': { blocks: '1 блок', pick_b1: 5, pick_b2: 0, b1_range: '1-36', b2_range: '-', example: '11.04.2026 23:00||2829||7,14,21,30,4||' },
}

// ── Animation variants ───────────────────────────────────────────────────────

export const fadeIn = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.3 },
}

/** Instant transition for users with prefers-reduced-motion */
export const fadeInInstant = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0 },
}

// ── Purge-safe color classes (dynamic bg-${color}-* would be purged) ─────

export const BLOCK_COLOR_CLASSES: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  blue: {
    bg: 'bg-blue-500/20',
    border: 'border-blue-500/40',
    text: 'text-blue-300',
    badge: 'bg-blue-500/20 text-blue-300 border-blue-500/20',
  },
  emerald: {
    bg: 'bg-emerald-500/20',
    border: 'border-emerald-500/40',
    text: 'text-emerald-300',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/20',
  },
}
