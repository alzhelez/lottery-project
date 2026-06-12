import { NextResponse } from 'next/server'
import { existsSync, readFileSync, writeFileSync, unlinkSync } from 'fs'
import { join } from 'path'
import { tmpdir } from 'os'
import { validateGameId, validateFilePath, safeParseStdout, getDrawsFilePath, errorJson } from '@/lib/api-utils'
import { runPythonScript } from '@/lib/python-runner'
import { rateLimit } from '@/lib/rate-limit'

// ── Types ────────────────────────────────────────────────────────────────────

interface RunConfig {
  draw_range?: number
  seed_size?: number
  batch_step: number
  full_every: number
  no_cv: boolean
  strategy: string
  label: string
}

interface RunAccuracy {
  last_50_avg: number
  baseline_random: number
  improvement_pct: number | null
}

interface PredictionInfo {
  total_draws_used: number
  draw_range: string | null
  last_draw_no: number | null
  next_draw_no: number | null
  game_key: string
}

interface IndividualRun {
  params: RunConfig
  prediction?: { block1: number[]; block2: number[] }
  consensus_strength?: { block1: number; block2: number }
  accuracy?: RunAccuracy | null
  backtest?: Record<string, unknown>
  game_format?: string
  total_draws?: number
  prediction_info?: PredictionInfo
  error?: string
}

interface MetaConsensusEntry {
  number: string
  strategyCount: number
  strategies: string[]
}

interface ConfidenceEntry {
  number: string
  confidence: number
}

interface GodModeResult {
  status: 'ok'
  frequency_b1: Record<string, number>
  frequency_b2: Record<string, number>
  top_numbers_b1: Array<{ number: string; count: number }>
  top_numbers_b2: Array<{ number: string; count: number }>
  /** v38.1: backtest-weighted top numbers */
  top_numbers_b1_weighted: Array<{ number: string; score: number }>
  top_numbers_b2_weighted: Array<{ number: string; score: number }>
  /** v38.2: Rank-weighted top numbers (top position = more points) */
  top_numbers_b1_ranked: Array<{ number: string; score: number }>
  top_numbers_b2_ranked: Array<{ number: string; score: number }>
  /** v38.2: Numbers supported by ≥3 different strategies */
  meta_consensus_b1: MetaConsensusEntry[]
  meta_consensus_b2: MetaConsensusEntry[]
  /** v38.2: Composite confidence 0–100 per number */
  confidence_b1: ConfidenceEntry[]
  confidence_b2: ConfidenceEntry[]
  /** Per-block consensus values (not just avg) */
  consensus_distribution: Array<{ block1: number; block2: number; avg: number }>
  avg_consensus_b1: number
  avg_consensus_b2: number
  best_run: IndividualRun | null
  worst_run: IndividualRun | null
  /** v38.1: best run by backtest accuracy */
  best_accuracy_run: IndividualRun | null
  /** v38.1: per-strategy performance summary */
  strategy_stats?: Array<{
    strategy: string
    count: number
    avg_consensus_b1: number
    avg_consensus_b2: number
    avg_accuracy: number
    avg_improvement: number
  }>
  runs_total: number
  runs_failed: number
  game_format?: string
  total_draws?: number
  prediction_info?: PredictionInfo
  individual_runs: IndividualRun[]
  /** v2: convergence detection — stability score and early-convergence hint */
  convergence?: {
    detected: boolean
    stability_score: number
    converged_at_run: number | null
  }
}

interface GodModeState {
  status: 'pending' | 'running' | 'done' | 'error'
  runs_completed: number
  runs_total: number
  runs_failed: number
  result?: GodModeResult
  error?: string
  startedAt: number
  /** v38.2.3: Track per-run durations for ETA calculation */
 lastRunStartedAt?: number
  avgRunDurationMs?: number
}

// ── Constants ────────────────────────────────────────────────────────────────

// ── v38.3.0: Server crash detection for polling ─────────────────────────────
// Store the last known startedAt per game so that when the server restarts
// (losing all globalThis state), polling can detect the discrepancy and stop.

const _GOD_MODE_STARTED_KEY = '__lottery_godModeStartedAt'

function getGodModeStartedAt(): Map<string, number> {
  const g = globalThis as Record<string, unknown>
  if (!g[_GOD_MODE_STARTED_KEY]) {
    g[_GOD_MODE_STARTED_KEY] = new Map<string, number>()
  }
  return g[_GOD_MODE_STARTED_KEY] as Map<string, number>
}

const godModeStartedAt = getGodModeStartedAt()

const POLLING_MAX_AGE_MS = 50 * 60 * 1000   // 50 minutes, well within STATE_TTL_MS of 60 min (v39.2.1)

const GOD_MODE_RATE_MAX = 1
const GOD_MODE_RATE_WINDOW_MS = 5 * 60 * 1000          // 5 minutes per game
// v39.2.1: 5 minutes per individual run (was 3 min — caused ~5/50 timeout failures
// with heavy configs: deep_training bs=300, draw_range=1000, stability dr=1000 ss=300)
const INDIVIDUAL_RUN_TIMEOUT_MS = 300_000               // 5 minutes per run
// v39.2.1: Dynamic total timeout — 4 min per run × maxRuns (was 2.5 min)
// With ~13.5k draws, heavy configs can take up to 4 min per run.
const RUN_TIME_BUDGET_MS = 240_000                       // 4 min budget per run
// v38.2.3: Allow up to 50 runs (user-selectable: 10, 20, 30, 50)
const MAX_INDIVIDUAL_RUNS = 50
const TOP_N = 20
const STATE_TTL_MS = 60 * 60 * 1000                    // 1 hour until state expires

// ── In-memory state (keyed by game name) ─────────────────────────────────────
// v38.2.4: Use globalThis to survive Next.js hot-reloads in dev mode.
// Without this, module re-evaluation recreates an empty Map, losing all state
// and causing God Mode progress to reset mid-run.

const _GOD_MODE_STATES_KEY = '__lottery_godModeStates'

function getGodModeStates(): Map<string, GodModeState> {
  const g = globalThis as Record<string, unknown>
  if (!g[_GOD_MODE_STATES_KEY]) {
    g[_GOD_MODE_STATES_KEY] = new Map<string, GodModeState>()
  }
  return g[_GOD_MODE_STATES_KEY] as Map<string, GodModeState>
}

const godModeStates = getGodModeStates()

// ── State cleanup ────────────────────────────────────────────────────────────

/** Evict old completed/errored states to prevent unbounded memory growth */
function cleanupOldStates(): void {
  const now = Date.now()
  const keysToDelete: string[] = []
  for (const [key, state] of godModeStates.entries()) {
    if (state.status !== 'running' && state.status !== 'pending') {
      if (now - state.startedAt > STATE_TTL_MS) {
        keysToDelete.push(key)
      }
    }
  }
  for (let i = 0; i < keysToDelete.length; i++) {
    godModeStates.delete(keysToDelete[i])
    godModeStartedAt.delete(keysToDelete[i])  // v39.2.1: prevent memory leak
  }
}

// ── Parameter generation ─────────────────────────────────────────────────────

/**
 * Generate up to `maxRuns` diverse parameter sets across 9 strategies:
 *   1. Draw range variation   (temp files with last N draws)        — 3 runs
 *   2. Batch-step variation   (--batch-step flag)                  — 5 runs
 *   3. Full-every variation   (--full-every flag)                  — 10 runs
 *   4. CV toggle variation    (--no-cv on/off)                     — 4 runs
 *   5. Combined variation     (draw range + batch step)            — 5 runs
 *   6. Stability-first        (conservative params, max agreement) — 5 runs
 *   7. Deep training          (large batch steps for depth)         — 6 runs
 *   8. Seed variation         (vary seed sizes)                    — 6 runs
 *   9. Precision              (small batch with CV enabled)        — 6 runs
 *
 * v38.2.3: Expanded from 32 to 50 max configs with 3 new strategies.
 */
function generateRunConfigs(maxRuns: number): RunConfig[] {
  const configs: RunConfig[] = []

  // ── Strategy 1: Vary draw ranges — 3 runs ──
  const drawRanges = [200, 500, 1000]
  for (let i = 0; i < drawRanges.length; i++) {
    if (configs.length >= maxRuns) return configs
    configs.push({
      draw_range: drawRanges[i],
      batch_step: 50,
      full_every: 5,
      no_cv: true,
      strategy: 'draw_range',
      label: `draw_range=${drawRanges[i]}, batch_step=50`,
    })
  }

  // ── Strategy 2: Vary --batch-step — 5 runs ────────────────
  const batchSteps = [25, 50, 75, 100, 150]
  for (let i = 0; i < batchSteps.length; i++) {
    if (configs.length >= maxRuns) return configs
    configs.push({
      batch_step: batchSteps[i],
      full_every: 5,
      no_cv: true,
      strategy: 'batch_step',
      label: `batch_step=${batchSteps[i]}, full_every=5`,
    })
  }

  // ── Strategy 3: Vary --full-every (1, 3, 5, 10) — 10 runs ───────────────
  const fullEveryValues = [1, 3, 5, 10]
  const batchStepsForFull = [50, 25, 75]
  for (let i = 0; i < fullEveryValues.length; i++) {
    const limit = i < 2 ? 3 : 2   // first two values get 3 runs, last two get 2
    for (let j = 0; j < limit; j++) {
      if (configs.length >= maxRuns) return configs
      configs.push({
        batch_step: batchStepsForFull[j],
        full_every: fullEveryValues[i],
        no_cv: j % 2 === 0,
        strategy: 'full_every',
        label: `full_every=${fullEveryValues[i]}, batch_step=${batchStepsForFull[j]}, no_cv=${j % 2 === 0}`,
      })
    }
  }

  // ── Strategy 4: With / without --no-cv — 4 runs ──────────
  // v39.2.0: Fixed — 2 runs with no_cv=true + 2 runs with no_cv=false (was all true)
  const cvToggleConfigs: Array<{ batch_step: number; no_cv: boolean }> = [
    { batch_step: 50, no_cv: true },
    { batch_step: 75, no_cv: false },
    { batch_step: 100, no_cv: true },
    { batch_step: 150, no_cv: false },
  ]
  for (const cvCfg of cvToggleConfigs) {
    if (configs.length >= maxRuns) return configs
    configs.push({
      batch_step: cvCfg.batch_step,
      full_every: 5,
      no_cv: cvCfg.no_cv,
      strategy: 'cv_toggle',
      label: `no_cv=${cvCfg.no_cv}, batch_step=${cvCfg.batch_step}`,
    })
  }

  // ── Strategy 5: Combined (draw range + batch step) — 5 runs ──
  const combos: Array<[number, number]> = [
    [200, 50], [500, 75], [1000, 25], [1000, 100], [300, 50],
  ]
  for (let i = 0; i < combos.length; i++) {
    if (configs.length >= maxRuns) return configs
    configs.push({
      draw_range: combos[i][0],
      batch_step: combos[i][1],
      full_every: 5,
      no_cv: true,
      strategy: 'combined',
      label: `draw_range=${combos[i][0]}, batch_step=${combos[i][1]}`,
    })
  }

  // ── Strategy 6: Stability-first — conservative params for max agreement ──
  const stabilityConfigs: Array<{ batch_step: number; full_every: number; no_cv: boolean; seed_size: number }> = [
    { batch_step: 50, full_every: 5, no_cv: true, seed_size: 200 },
    { batch_step: 100, full_every: 5, no_cv: true, seed_size: 200 },
    { batch_step: 50, full_every: 3, no_cv: true, seed_size: 300 },
    { batch_step: 75, full_every: 5, no_cv: true, seed_size: 200 },
    { batch_step: 50, full_every: 10, no_cv: true, seed_size: 150 },
  ]
  for (let i = 0; i < stabilityConfigs.length; i++) {
    if (configs.length >= maxRuns) return configs
    const s = stabilityConfigs[i]
    configs.push({
      draw_range: 1000,  // use maximum data for stability
      seed_size: s.seed_size,
      batch_step: s.batch_step,
      full_every: s.full_every,
      no_cv: s.no_cv,
      strategy: 'stability',
      label: `stability: dr=1000, bs=${s.batch_step}, fe=${s.full_every}, ss=${s.seed_size}`,
    })
  }

  // ── Strategy 7: Deep training — large batch steps for more thorough training ──
  // v38.2.3: New strategy — 6 runs
  const deepConfigs: Array<{ batch_step: number; full_every: number }> = [
    { batch_step: 200, full_every: 1 },
    { batch_step: 200, full_every: 5 },
    { batch_step: 250, full_every: 1 },
    { batch_step: 250, full_every: 5 },
    { batch_step: 300, full_every: 1 },
    { batch_step: 300, full_every: 5 },
  ]
  for (let i = 0; i < deepConfigs.length; i++) {
    if (configs.length >= maxRuns) return configs
    const d = deepConfigs[i]
    configs.push({
      draw_range: 1000,
      batch_step: d.batch_step,
      full_every: d.full_every,
      no_cv: true,
      strategy: 'deep_training',
      label: `deep: bs=${d.batch_step}, fe=${d.full_every}`,
    })
  }

  // ── Strategy 8: Seed variation — vary seed sizes with fixed params ──
  // v38.2.3: New strategy — 6 runs
  const seedVariations = [50, 100, 150, 250, 400, 500]
  for (let i = 0; i < seedVariations.length; i++) {
    if (configs.length >= maxRuns) return configs
    configs.push({
      draw_range: 500,
      seed_size: seedVariations[i],
      batch_step: 75,
      full_every: 3,
      no_cv: true,
      strategy: 'seed_variation',
      label: `seed: ss=${seedVariations[i]}, bs=75, fe=3`,
    })
  }

  // ── Strategy 9: Precision — small batch steps with CV enabled ──
  // v38.2.3: New strategy — 6 runs
  const precisionConfigs: Array<{ batch_step: number; full_every: number }> = [
    { batch_step: 25, full_every: 1 },
    { batch_step: 25, full_every: 3 },
    { batch_step: 25, full_every: 5 },
    { batch_step: 50, full_every: 1 },
    { batch_step: 50, full_every: 3 },
    { batch_step: 50, full_every: 5 },
  ]
  for (let i = 0; i < precisionConfigs.length; i++) {
    if (configs.length >= maxRuns) return configs
    const p = precisionConfigs[i]
    configs.push({
      draw_range: 500,
      batch_step: p.batch_step,
      full_every: p.full_every,
      no_cv: false,
      strategy: 'precision',
      label: `precision: bs=${p.batch_step}, fe=${p.full_every}, cv=true`,
    })
  }

  return configs
}

// ── Temp file helpers ────────────────────────────────────────────────────────

/**
 * Create a temporary draw file containing only the last `n` draw lines.
 * Returns the temp file path, or the original path if n >= available draws.
 * Returns null on I/O error.
 */
function createDrawRangeFile(originalPath: string, n: number): string | null {
  try {
    const content = readFileSync(originalPath, 'utf-8')
    const allLines = content.split('\n').filter(
      (line: string) => line.trim() && line.includes('||'),
    )
    if (allLines.length <= n) {
      // No need for a temp file — original already has ≤ n draws
      return originalPath
    }
    const lastN = allLines.slice(-n)
    const tempPath = join(tmpdir(), `godmode_${Date.now()}_${n}.txt`)
    writeFileSync(tempPath, lastN.join('\n') + '\n', 'utf-8')
    return tempPath
  } catch (err) {
    console.error(`[god-mode] Failed to create draw-range file (n=${n}):`, err)
    return null
  }
}

/** Remove a temp file only if it resides in an OS temp directory */
function cleanupTempFile(filePath: string): void {
  if (!filePath) return
  try {
    if (filePath.startsWith(tmpdir()) || filePath.startsWith('/tmp/')) {
      unlinkSync(filePath)
    }
  } catch {
    // Best-effort cleanup — ignore errors
  }
}

// ── Build predict.py command arguments ───────────────────────────────────────

function buildPredictArgs(filePath: string, config: RunConfig): string[] {
  const args: string[] = ['--file', filePath]
  if (config.no_cv) {
    args.push('--no-cv')
  }
  args.push('--batch-step', String(config.batch_step))
  args.push('--full-every', String(config.full_every))
  if (config.seed_size !== undefined) {
    args.push('--seed-size', String(config.seed_size))
  }
  // v39.3.1: Always use --god-mode flag for speed optimizations
  args.push('--god-mode')
  return args
}

// ── Execute a single predict.py run ──────────────────────────────────────────

async function executeSingleRun(
  filePath: string,
  config: RunConfig,
): Promise<IndividualRun> {
  let actualFilePath = filePath
  let createdTempFile = false

  // Create a truncated temp file if draw_range is specified
  if (config.draw_range !== undefined && config.draw_range > 0) {
    const tempPath = createDrawRangeFile(filePath, config.draw_range)
    if (tempPath === null) {
      return {
        params: config,
        error: `Failed to create temp file for draw_range=${config.draw_range}`,
      }
    }
    if (tempPath !== filePath) {
      actualFilePath = tempPath
      createdTempFile = true
    }
  }

  try {
    const args = buildPredictArgs(actualFilePath, config)
    console.log(`[god-mode] Running: ${config.label}`)

    const { stdout, stderr, code } = await runPythonScript('predict.py', args, {
      timeout: INDIVIDUAL_RUN_TIMEOUT_MS,
    })

    // Non-zero exit code or killed process (code === null from SIGKILL)
    if (code === null || code !== 0) {
      const reason = code === null ? 'Process killed (timeout)' : `exit code ${code}`
      const snippet = stderr ? stderr.slice(-300) : reason
      console.warn(`[god-mode] FAILED (${config.label}): ${snippet}`)
      return { params: config, error: `Script error: ${reason}${stderr ? ': ' + stderr.slice(-100) : ''}` }
    }

    // Parse JSON output
    const parsed = safeParseStdout(stdout || '')
    if (!parsed || !parsed.data) {
      console.warn(`[god-mode] PARSE ERROR (${config.label}): ${parsed?.error}`)
      return { params: config, error: parsed?.error || 'Failed to parse script output' }
    }

    const data = parsed.data

    // v38.2.6: Fix consensus extraction — predict.py nests consensus inside
    // data.prediction, NOT at the top level. Previous code read from the wrong
    // path, always getting undefined → 0, making all God Mode consensus 0%.
    const predData = (typeof data.prediction === 'object' && data.prediction !== null)
      ? data.prediction as Record<string, unknown>
      : undefined
    const rawB1 = typeof predData?.consensus_agreement_b1 === 'number' ? predData.consensus_agreement_b1 as number : 0
    const rawB2 = typeof predData?.consensus_agreement_b2 === 'number' ? predData.consensus_agreement_b2 as number : 0

    // v38.2.6: Extract accuracy from data.accuracy (last_50_avg, baseline_random, improvement_pct)
    const accData = (typeof data.accuracy === 'object' && data.accuracy !== null)
      ? data.accuracy as Record<string, unknown>
      : undefined
    const accuracy: RunAccuracy | undefined = accData
      ? {
          last_50_avg: typeof accData.last_50_avg === 'number' ? accData.last_50_avg as number : 0,
          baseline_random: typeof accData.baseline_random === 'number' ? accData.baseline_random as number : 0,
          improvement_pct: typeof accData.improvement_pct === 'number' ? accData.improvement_pct as number : null,
        }
      : undefined

    // Extract structured fields
    const result: IndividualRun = {
      params: config,
      prediction: {
        block1: Array.isArray(predData?.block1) ? predData.block1 as number[] : [],
        block2: Array.isArray(predData?.block2) ? predData.block2 as number[] : [],
      },
      consensus_strength: { block1: rawB1, block2: rawB2 },
      accuracy,
      backtest: typeof data.backtest === 'object' && data.backtest !== null
        ? (data.backtest as Record<string, unknown>)
        : undefined,
      // v38.2.6: game_format is an object { pick_b1, pick_b2, ... }, not a string
      game_format: typeof data.game_format === 'object' && data.game_format !== null
        ? JSON.stringify(data.game_format)
        : undefined,
      // v38.2.6: total_draws lives inside data.data_quality, not at top level
      total_draws: typeof (data.data_quality as any)?.total_draws === 'number'
        ? (data.data_quality as any).total_draws as number
        : undefined,
      // v39.4.0: prediction_info (data used + next draw)
      prediction_info: typeof data.prediction_info === 'object' && data.prediction_info !== null
        ? data.prediction_info as PredictionInfo
        : undefined,
    }

    return result
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error'
    console.error(`[god-mode] EXCEPTION (${config.label}):`, msg)
    return { params: config, error: msg }
  } finally {
    if (createdTempFile) {
      cleanupTempFile(actualFilePath)
    }
  }
}

// ── v38.2: Rank-based scoring helper ────────────────────────────────────────

/** Compute rank-based score for a prediction block.
 *  Number at position 0 gets `pick` points, position 1 gets `pick-1`, etc.
 *  This rewards numbers that appear at the TOP of predictions.
 */
function rankScore(numbers: number[], pick: number): Map<number, number> {
  const scores = new Map<number, number>()
  for (let i = 0; i < numbers.length; i++) {
    const n = numbers[i]
    const score = Math.max(1, pick - i)  // top = pick, bottom = 1
    scores.set(n, (scores.get(n) || 0) + score)
  }
  return scores
}

// ── Compute run weight for backtest-weighted aggregation ─────────────────────

/**
 * v38.1: Compute a weight for each run based on backtest performance and
 * internal consensus strength. Runs that are both accurate AND internally
 * consistent get the most influence in the weighted aggregation.
 */
function computeRunWeight(run: IndividualRun, avgBaseline: number): number {
  if (!run.accuracy || run.accuracy.last_50_avg <= 0) return 1.0

  const baseline = run.accuracy.baseline_random > 0 ? run.accuracy.baseline_random : avgBaseline
  if (baseline <= 0) return 1.0

  const accuracyRatio = run.accuracy.last_50_avg / baseline

  const cs = run.consensus_strength
  const avgConsensus = cs ? (cs.block1 + cs.block2) / 2 : 0
  const consensusFactor = 0.5 + 0.5 * avgConsensus

  return Math.max(0.3, Math.min(4.0, accuracyRatio * consensusFactor))
}

// ── v2: Convergence detection helper ──────────────────────────────────────

/**
 * Check if the top-N predicted numbers have stabilized across the most recent runs.
 * Efficient O(N * pick) intersection check — no O(n²) loops.
 *
 * @param completedRuns - successful runs in execution order
 * @param pickB1 - number of picks for block1
 * @param pickB2 - number of picks for block2
 * @returns convergence info: whether converged, stability score (0–1), and run number
 */
function checkConvergence(
  completedRuns: Array<{ prediction: { block1: number[]; block2: number[] } }>,
  pickB1: number,
  pickB2: number,
): { converged: boolean; stabilityScore: number; convergedAtRun: number | null } {
  const total = completedRuns.length
  const n = Math.min(8, total)
  if (n < 2) return { converged: false, stabilityScore: 0, convergedAtRun: null }

  const lastN = completedRuns.slice(-n)

  // Compute intersection of top-pickB1 numbers across all last-N runs (block1)
  let stableB1: Set<number> | null = null
  for (let i = 0; i < lastN.length; i++) {
    const topNumbers = lastN[i].prediction.block1.slice(0, pickB1)
    const set = new Set(topNumbers)
    if (stableB1 === null) {
      stableB1 = set
    } else {
      // Intersect: keep only numbers present in both sets
      stableB1 = new Set([...stableB1].filter(x => set.has(x)))
    }
  }

  // Compute intersection of top-pickB2 numbers across all last-N runs (block2)
  let stableB2: Set<number> | null = null
  const hasB2 = lastN.some(r => r.prediction.block2.length > 0)
  if (hasB2 && pickB2 > 0) {
    for (let i = 0; i < lastN.length; i++) {
      const topNumbers = lastN[i].prediction.block2.slice(0, pickB2)
      const set = new Set(topNumbers)
      if (stableB2 === null) {
        stableB2 = set
      } else {
        stableB2 = new Set([...stableB2].filter(x => set.has(x)))
      }
    }
  }

  const scoreB1 = pickB1 > 0 ? (stableB1?.size || 0) / pickB1 : 0
  const scoreB2 = hasB2 && pickB2 > 0 ? (stableB2?.size || 0) / pickB2 : 0

  const stabilityScore = Math.max(scoreB1, scoreB2)
  const converged = stabilityScore >= 0.75

  // converged_at_run = the earliest run in the converging window (1-indexed)
  const convergedAtRun = converged ? total - n + 1 : null

  return {
    converged,
    stabilityScore: Math.round(stabilityScore * 100) / 100,
    convergedAtRun,
  }
}

// ── Aggregate all individual run results ─────────────────────────────────────

function aggregateResults(runs: IndividualRun[]): GodModeResult {
  // Unweighted frequency counting (backward compatible)
  const frequency_b1: Record<string, number> = {}
  const frequency_b2: Record<string, number> = {}

  // v38.2: Rank-weighted score accumulation (Task D)
  const rank_b1 = new Map<number, number>()
  const rank_b2 = new Map<number, number>()

  // v38.2: Strategy support tracking (Task F)
  const strategySupport_b1: Record<string, Set<string>> = {}
  const strategySupport_b2: Record<string, Set<string>> = {}

  const consensusValues: Array<{ avg: number; b1: number; b2: number }> = []
  let gameFormat: string | undefined
  let totalDraws: number | undefined
  let predictionInfo: PredictionInfo | undefined

  // v38.1: Weighted frequency (backtest-weighted)
  const weightedFreq_b1: Record<string, number> = {}
  const weightedFreq_b2: Record<string, number> = {}

  // v38.1: Per-strategy stats buckets
  const strategyBuckets: Record<string, Array<{ b1: number; b2: number; accuracy: number; improvement: number | null }>> = {}

  // v2: Track completed (successful) runs for convergence detection
  const completedRuns: IndividualRun[] = []

  let bestRun: IndividualRun | null = null
  let worstRun: IndividualRun | null = null
  let bestAccuracyRun: IndividualRun | null = null
  let bestAvg = -Infinity
  let worstAvg = Infinity
  let bestAccuracyScore = -Infinity
  let runsFailed = 0

  // v38.2: Determine pick counts from first successful run
  let pickB1 = 4
  let pickB2 = 4
  let pickDetermined = false

  // v38.1: Compute average baseline across all successful runs
  let baselineSum = 0
  let baselineCount = 0

  for (let i = 0; i < runs.length; i++) {
    const run = runs[i]

    // Skip failed or incomplete runs
    // v39.3.1: Allow empty block2 for single-block games (pick_b2=0)
    const hasB1 = run.prediction.block1.length > 0
    const hasB2 = run.prediction.block2.length > 0
    const isSingleBlock = !hasB2  // single-block game has no block2 numbers

    if (run.error || !run.prediction || !run.consensus_strength || !hasB1) {
      runsFailed++
      continue
    }

    const b1 = run.prediction.block1
    const b2 = run.prediction.block2

    // v38.2: Capture pick counts from first successful run
    if (!pickDetermined) {
      pickB1 = b1.length > 0 ? b1.length : 4
      pickB2 = b2.length > 0 ? b2.length : 4
      pickDetermined = true
    }

    // v38.1: Accumulate baseline for weighted aggregation
    if (run.accuracy) {
      const bl = run.accuracy.baseline_random
      if (bl > 0) {
        baselineSum += bl
        baselineCount++
      }
    }

    // v2: Recency weighting — last 10 executed runs get 1.1x weight
    const runWeight = i >= runs.length - 10 ? 1.1 : 1.0

    // Tally block1 frequency with recency weighting
    for (let j = 0; j < b1.length; j++) {
      const key = String(b1[j])
      frequency_b1[key] = (frequency_b1[key] || 0) + runWeight
    }

    // Tally block2 frequency with recency weighting
    for (let j = 0; j < b2.length; j++) {
      const key = String(b2[j])
      frequency_b2[key] = (frequency_b2[key] || 0) + runWeight
    }

    // v2: Record successful run for convergence detection
    completedRuns.push(run)

    // v38.2 Task D: Accumulate rank-based scores
    const b1Scores = rankScore(b1, pickB1)
    for (const [num, score] of b1Scores) {
      rank_b1.set(num, (rank_b1.get(num) || 0) + score)
    }
    if (b2.length > 0) {
      const b2Scores = rankScore(b2, pickB2)
      for (const [num, score] of b2Scores) {
        rank_b2.set(num, (rank_b2.get(num) || 0) + score)
      }
    }

    // v38.2 Task F: Track strategy support per number
    const runStrategy = run.params.strategy || 'unknown'
    for (let j = 0; j < b1.length; j++) {
      const key = String(b1[j])
      if (!strategySupport_b1[key]) strategySupport_b1[key] = new Set()
      strategySupport_b1[key].add(runStrategy)
    }
    for (let j = 0; j < b2.length; j++) {
      const key = String(b2[j])
      if (!strategySupport_b2[key]) strategySupport_b2[key] = new Set()
      strategySupport_b2[key].add(runStrategy)
    }

    // Consensus tracking
    const cs = run.consensus_strength
    const avg = (cs.block1 + cs.block2) / 2
    consensusValues.push({ avg, b1: cs.block1, b2: cs.block2 })

    // v38.1: Per-strategy stats
    if (!strategyBuckets[runStrategy]) strategyBuckets[runStrategy] = []
    strategyBuckets[runStrategy].push({
      b1: cs.block1,
      b2: cs.block2,
      accuracy: run.accuracy?.last_50_avg ?? 0,
      improvement: run.accuracy?.improvement_pct ?? null,
    })

    if (avg > bestAvg) {
      bestAvg = avg
      bestRun = run
    }
    if (avg < worstAvg) {
      worstAvg = avg
      worstRun = run
    }

    // v38.1: Track best by accuracy
    if (run.accuracy && run.accuracy.last_50_avg > bestAccuracyScore) {
      bestAccuracyScore = run.accuracy.last_50_avg
      bestAccuracyRun = run
    }

    // Capture metadata from last successful run
    if (run.game_format) gameFormat = run.game_format
    if (run.total_draws !== undefined) totalDraws = run.total_draws
    if (run.prediction_info) predictionInfo = run.prediction_info
  }

  // v2: Convergence detection — check if top numbers have stabilized
  const convergenceResult = checkConvergence(completedRuns, pickB1, pickB2)
  if (convergenceResult.converged) {
    console.log(
      `[god-mode] CONVERGENCE DETECTED at run ${convergenceResult.convergedAtRun} ` +
      `(stability_score=${convergenceResult.stabilityScore}). ` +
      `Continuing all runs for diversity.`,
    )
  }

  // v38.1: Compute average baseline across all successful runs
  const avgBaseline = baselineCount > 0 ? baselineSum / baselineCount : 1.0

  // v38.1: Second pass — compute weighted frequencies using now-known avgBaseline
  for (let i = 0; i < runs.length; i++) {
    const run = runs[i]
    // v39.3.1: Skip empty predictions in weighted pass too (allow empty block2 for single-block)
    if (run.error || !run.prediction || !run.consensus_strength ||
        run.prediction.block1.length === 0) continue
    const weight = computeRunWeight(run, avgBaseline)
    for (let j = 0; j < run.prediction.block1.length; j++) {
      const key = String(run.prediction.block1[j])
      weightedFreq_b1[key] = (weightedFreq_b1[key] || 0) + weight
    }
    for (let j = 0; j < run.prediction.block2.length; j++) {
      const key = String(run.prediction.block2[j])
      weightedFreq_b2[key] = (weightedFreq_b2[key] || 0) + weight
    }
  }

  // Build sorted top-N lists (unweighted, backward compatible)
  const top_numbers_b1 = Object.entries(frequency_b1)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N)
    .map(([number, count]) => ({ number, count }))

  const top_numbers_b2 = Object.entries(frequency_b2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N)
    .map(([number, count]) => ({ number, count }))

  // v38.2 Task D: Build rank-weighted top-N lists
  const top_numbers_b1_ranked = [...rank_b1.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N)
    .map(([number, score]) => ({ number: String(number), score }))

  const top_numbers_b2_ranked = [...rank_b2.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N)
    .map(([number, score]) => ({ number: String(number), score }))

  // v38.2.2: Dynamic meta-consensus threshold based on run count
  // With 6 strategies and N runs, expect ~N/6 runs per strategy
  // Threshold = max(2, ceil(num_strategies * 0.4))
  // For 10 runs: max(2, ceil(6*0.4)) = max(2, 3) = 3
  // For 32 runs: max(2, ceil(6*0.4)) = 3 (same, but more runs = higher counts)
  const numStrategies = new Set<string>()
  for (const run of runs) {
    if (!run.error && run.prediction) numStrategies.add(run.params.strategy || 'unknown')
  }
  const metaThreshold = Math.max(2, Math.ceil(numStrategies.size * 0.4))

  const meta_consensus_b1: MetaConsensusEntry[] = Object.entries(strategySupport_b1)
    .filter(([, strategies]) => strategies.size >= metaThreshold)
    .sort((a, b) => b[1].size - a[1].size)
    .slice(0, TOP_N)
    .map(([number, strategies]) => ({
      number,
      strategyCount: strategies.size,
      strategies: [...strategies],
    }))

  const meta_consensus_b2: MetaConsensusEntry[] = Object.entries(strategySupport_b2)
    .filter(([, strategies]) => strategies.size >= metaThreshold)
    .sort((a, b) => b[1].size - a[1].size)
    .slice(0, TOP_N)
    .map(([number, strategies]) => ({
      number,
      strategyCount: strategies.size,
      strategies: [...strategies],
    }))

  // v38.2 Task H: Confidence scores (composite 0–100)
  const maxFreqB1 = top_numbers_b1.length > 0 ? top_numbers_b1[0].count : 1
  const maxFreqB2 = top_numbers_b2.length > 0 ? top_numbers_b2[0].count : 1
  const maxRankB1 = top_numbers_b1_ranked.length > 0 ? top_numbers_b1_ranked[0].score : 1
  const maxRankB2 = top_numbers_b2_ranked.length > 0 ? top_numbers_b2_ranked[0].score : 1

  const confidence_b1: ConfidenceEntry[] = Object.entries(frequency_b1)
    .map(([number, count]) => {
      const weighted = rank_b1.get(Number(number)) || 0
      const stratCount = strategySupport_b1[number]?.size || 0
      const freqNorm = count / maxFreqB1
      const weightNorm = maxRankB1 > 0 ? weighted / maxRankB1 : 0
      const stratFactor = Math.min(1, stratCount / 4)
      const rankFactor = weighted > 0 ? Math.min(1, weighted / (pickB1 || 4)) : 0
      const confidence = Math.round(
        (freqNorm * 0.3 + weightNorm * 0.3 + stratFactor * 0.2 + rankFactor * 0.2) * 100,
      )
      return { number, confidence }
    })
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, TOP_N)

  const confidence_b2: ConfidenceEntry[] = Object.entries(frequency_b2)
    .map(([number, count]) => {
      const weighted = rank_b2.get(Number(number)) || 0
      const stratCount = strategySupport_b2[number]?.size || 0
      const freqNorm = count / maxFreqB2
      const weightNorm = maxRankB2 > 0 ? weighted / maxRankB2 : 0
      const stratFactor = Math.min(1, stratCount / 4)
      const rankFactor = weighted > 0 ? Math.min(1, weighted / (pickB2 || 4)) : 0
      const confidence = Math.round(
        (freqNorm * 0.3 + weightNorm * 0.3 + stratFactor * 0.2 + rankFactor * 0.2) * 100,
      )
      return { number, confidence }
    })
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, TOP_N)

  // v38.2: Consensus distribution with per-block breakdown (restored from v38.1 format)
  const consensus_distribution = consensusValues.map(v => ({
    block1: Math.round(v.b1 * 100) / 100,
    block2: Math.round(v.b2 * 100) / 100,
    avg: Math.round(v.avg * 100) / 100,
  }))
  const avgConsensusB1 = consensusValues.length > 0
    ? consensusValues.reduce((sum, v) => sum + v.b1, 0) / consensusValues.length
    : 0
  const avgConsensusB2 = consensusValues.length > 0
    ? consensusValues.reduce((sum, v) => sum + v.b2, 0) / consensusValues.length
    : 0

  // v38.1: Build weighted top-N lists
  const top_numbers_b1_weighted = Object.entries(weightedFreq_b1)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N)
    .map(([number, score]) => ({ number, score }))

  const top_numbers_b2_weighted = Object.entries(weightedFreq_b2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N)
    .map(([number, score]) => ({ number, score }))

  // v38.1: Build strategy stats summary
  const strategy_stats = Object.entries(strategyBuckets).map(([strategy, bucket]) => {
    const avgB1 = bucket.reduce((s, v) => s + v.b1, 0) / bucket.length
    const avgB2 = bucket.reduce((s, v) => s + v.b2, 0) / bucket.length
    const avgAcc = bucket.reduce((s, v) => s + v.accuracy, 0) / bucket.length
    const improvements = bucket.filter(v => v.improvement !== null).map(v => v.improvement as number)
    const avgImp = improvements.length > 0
      ? improvements.reduce((s, v) => s + v, 0) / improvements.length
      : 0
    return {
      strategy,
      count: bucket.length,
      avg_consensus_b1: Math.round(avgB1 * 100) / 100,
      avg_consensus_b2: Math.round(avgB2 * 100) / 100,
      avg_accuracy: Math.round(avgAcc * 100) / 100,
      avg_improvement: Math.round(avgImp * 100) / 100,
    }
  })

  return {
    status: 'ok',
    frequency_b1,
    frequency_b2,
    top_numbers_b1,
    top_numbers_b2,
    top_numbers_b1_weighted,
    top_numbers_b2_weighted,
    top_numbers_b1_ranked,
    top_numbers_b2_ranked,
    meta_consensus_b1,
    meta_consensus_b2,
    confidence_b1,
    confidence_b2,
    consensus_distribution,
    avg_consensus_b1: Math.round(avgConsensusB1 * 100) / 100,
    avg_consensus_b2: Math.round(avgConsensusB2 * 100) / 100,
    best_run: bestRun,
    worst_run: worstRun,
    best_accuracy_run: bestAccuracyRun,
    strategy_stats,
    runs_total: runs.length,
    runs_failed: runsFailed,
    game_format: gameFormat,
    total_draws: totalDraws,
    prediction_info: predictionInfo,
    individual_runs: runs,
    convergence: {
      detected: convergenceResult.converged,
      stability_score: convergenceResult.stabilityScore,
      converged_at_run: convergenceResult.convergedAtRun,
    },
  }
}

// ── Background God Mode executor ─────────────────────────────────────────────

async function executeGodMode(
  game: string,
  filePath: string,
  maxRuns: number,
): Promise<void> {
  const state = godModeStates.get(game)
  if (!state) return   // state was cleared while we were queued

  // v39.2.1: Declare results outside try so catch can aggregate partial results
  let results: IndividualRun[] = []

  try {
    const configs = generateRunConfigs(maxRuns)
    state.runs_total = configs.length
    state.status = 'running'

    // v39.2.0: Dynamic total timeout based on actual run count
    const totalTimeoutMs = configs.length * RUN_TIME_BUDGET_MS

    console.log(
      `[god-mode] ${game}: starting ${configs.length} runs ` +
      `(timeout: ${Math.round(totalTimeoutMs / 60000)}min, strategies: draw_range, batch_step, full_every, cv_toggle, combined, stability, deep, seed, precision)`,
    )

    results = []
    const runDurations: number[] = []

    for (let i = 0; i < configs.length; i++) {
      // Guard: total timeout check (v39.2.0: dynamic based on run count)
      const elapsed = Date.now() - state.startedAt
      if (elapsed > totalTimeoutMs) {
        console.warn(
          `[god-mode] ${game}: total timeout (${Math.round(totalTimeoutMs / 1000)}s) ` +
          `reached after ${i}/${configs.length} runs`,
        )
        // Use return to exit the function (no break outside loop issue)
        state.result = aggregateResults(results)
        state.status = 'done'
        state.error = `Total timeout reached after ${i} runs`
        return
      }

      // Guard: state was cleared (e.g., restart requested)
      if (!godModeStates.has(game)) {
        console.log(`[god-mode] ${game}: state cleared externally, aborting`)
        return
      }

      // v38.3.0: Guard: check if STOP was requested via cancel button
      if (state.status === 'done') {
        console.log(`[god-mode] ${game}: STOP detected via cancel, aborting after ${i} runs`)
        return
      }

      // v38.2.3: Track per-run start time for ETA
      const runStart = Date.now()
      state.lastRunStartedAt = runStart

      // v38.2.4: Secondary timeout with proper cleanup — skip hung runs
      let run: IndividualRun
      let secondaryTimer: ReturnType<typeof setTimeout> | undefined
      try {
        const secondaryTimeout = new Promise<IndividualRun>((_, reject) => {
          secondaryTimer = setTimeout(
            () => reject(new Error('Run exceeded timeout + grace period')),
            INDIVIDUAL_RUN_TIMEOUT_MS + 15_000,
          )
        })
        run = await Promise.race([
          executeSingleRun(filePath, configs[i]),
          secondaryTimeout,
        ])
      } catch {
        // Secondary timeout hit — log and create a failed run
        console.error(`[god-mode] ${game}: [${i + 1}/${configs.length}] SECONDARY TIMEOUT — ${configs[i].label}`)
        run = { params: configs[i], error: 'Run timed out (secondary timeout)' }
      } finally {
        // v38.2.4: Always clean up the secondary timer to prevent memory leaks
        if (secondaryTimer) clearTimeout(secondaryTimer)
      }

      // v38.2.3: Record run duration for ETA
      const runDuration = Date.now() - runStart
      runDurations.push(runDuration)
      state.avgRunDurationMs = runDurations.reduce((a, b) => a + b, 0) / runDurations.length

      results.push(run)
      state.runs_completed = i + 1
      // v38.3.0: Bug #7 — incremental counter instead of O(n²) filter
      if (run.error) {
        state.runs_failed = (state.runs_failed || 0) + 1
      }

      // v39.3.1: Aggregate partial results after each run so STOP can return data
      state.result = aggregateResults(results)

      console.log(
        `[god-mode] ${game}: [${i + 1}/${configs.length}] ` +
        `${run.error ? 'FAILED' : 'OK'} — ${configs[i].label} (${(runDuration / 1000).toFixed(1)}s)` +
        `${run.error ? ` — ${run.error.slice(0, 150)}` : ''}`,
      )
    }

    // All runs completed (or total timeout hit via the guard above)
    state.result = aggregateResults(results)
    state.status = 'done'

    const successful = results.length - (state.runs_failed || 0)
    console.log(
      `[god-mode] ${game}: finished. ${successful}/${results.length} runs ` +
      `succeeded, ${state.runs_failed} failed.`,
    )
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error'
    console.error(`[god-mode] ${game}: unhandled error:`, msg)
    // v39.2.1: Aggregate partial results even on error
    if (results.length > 0) {
      state.result = aggregateResults(results)
    }
    state.status = 'error'
    state.error = msg
  }
}

// ── POST handler ─────────────────────────────────────────────────────────────

export async function POST(request: Request) {
  // Periodically evict stale states
  cleanupOldStates()

  try {
    const body = await request.json()
    const { game, data_file, max_runs, restart, stop } = body

    // ── v38.3.0: Fast-path: handle STOP request ──────────────────────────
    // Bug #1: Cancel button now actually works — deletes state to abort runs.
    if (stop && typeof game === 'string') {
      const st = godModeStates.get(game)
      if (st) {
        const wasRunning = st.status === 'running' || st.status === 'pending'
        st.status = 'done'
        st.error = 'Cancelled by user'
        console.log(`[god-mode] ${game}: STOP requested (was ${wasRunning ? 'running' : st.status})`)
        // v39.3.1: Aggregate partial results on STOP so user sees what was completed
        if (wasRunning && st.runs_completed > 0 && st.result) {
          // result already contains aggregated data from completed runs
        }
        return NextResponse.json({
          status: 'done',
          error: 'Cancelled by user',
          runs_completed: st.runs_completed,
          runs_total: st.runs_total,
          runs_failed: st.runs_failed,
          _refreshing: false,
          _cancelled: true,
        })
      }
      // No state found — nothing to stop
      return NextResponse.json({ status: 'done', _refreshing: false, _cancelled: true })
    }

    // ── Fast-path: polling for an active or completed God Mode run ────────
    // Skip full validation when simply checking progress (game string presence only)
    if (typeof game === 'string' && game.length > 0 && game.length <= 50 && !restart) {
      // v38.3.0: Bug #9 — detect server crash/restart
      // Client sends started_at in body during polling. If no state exists but
      // started_at is recent, the server likely restarted and lost state.
      const clientStartedAt = body.started_at
      if (!godModeStates.has(game) && typeof clientStartedAt === 'number') {
        const age = Date.now() - clientStartedAt
        if (age > 5000 && age < POLLING_MAX_AGE_MS) {
          // Server lost state while client still polling — report real failure
          console.warn(`[god-mode] ${game}: server crash detected (client started_at=${clientStartedAt}, age=${Math.round(age / 1000)}s)`)
          return NextResponse.json(
            {
              status: 'error',
              error: 'Сервер перезапустился. Состояние Режима Бога потеряно. Пожалуйста, запустите заново.',
              runs_completed: 0,
              runs_total: 0,
              runs_failed: 0,
              _refreshing: false,
              _server_crash: true,
            },
            { status: 500 },
          )
        }
      }

      const existingState = godModeStates.get(game)

      if (existingState) {
        // Still running or just started — return progress
        if (existingState.status === 'running' || existingState.status === 'pending') {
          return NextResponse.json({
            status: existingState.status,
            runs_completed: existingState.runs_completed,
            runs_total: existingState.runs_total,
            runs_failed: existingState.runs_failed,
            // v38.2.3: Include timing info for ETA calculation
            started_at: existingState.startedAt,
            avg_run_duration_ms: existingState.avgRunDurationMs,
            _refreshing: true,
            _message:
              existingState.status === 'pending'
                ? 'God Mode initializing...'
                : `Running ${existingState.runs_completed}/${existingState.runs_total}...`,
          })
        }

        // Completed successfully — return full aggregated result
        if (existingState.status === 'done' && existingState.result) {
          return NextResponse.json({
            ...existingState.result,
            _refreshing: false,
          })
        }

        // Finished with error — return error details
        if (existingState.status === 'error') {
          return NextResponse.json(
            {
              status: 'error',
              error: existingState.error || 'God Mode run failed',
              runs_completed: existingState.runs_completed,
              runs_total: existingState.runs_total,
              runs_failed: existingState.runs_failed,
              _refreshing: false,
            },
            { status: 500 },
          )
        }

        // v39.2.1: Cancelled or completed without result — don't restart
        if (existingState.status === 'done' && !existingState.result) {
          return NextResponse.json({
            status: 'done',
            error: existingState.error || 'Run cancelled',
            runs_completed: existingState.runs_completed,
            runs_total: existingState.runs_total,
            runs_failed: existingState.runs_failed,
            _refreshing: false,
            _cancelled: true,
          })
        }
      }
    }

    // ── New run or restart — apply rate limit ─────────────────────────────
    const rl = rateLimit(
      `godmode-${typeof game === 'string' ? game : 'unknown'}`,
      GOD_MODE_RATE_MAX,
      GOD_MODE_RATE_WINDOW_MS,
    )
    if (!rl.allowed) {
      return errorJson(
        `God Mode rate limit reached. Please wait ${Math.ceil(rl.resetIn / 1000)}s before trying again.`,
        429,
        { retry_after: Math.ceil(rl.resetIn / 1000) },
      )
    }

    // ── Validate game identifier ──────────────────────────────────────────
    const gameErr = validateGameId(game)
    if (gameErr) return errorJson(gameErr, 400)

    // ── Resolve data file path ────────────────────────────────────────────
    const file = data_file || (game ? getDrawsFilePath(game) : null)
    if (file) {
      const fileErr = validateFilePath(file)
      if (fileErr) return errorJson(fileErr, 400)
    }
    if (!file) {
      return errorJson('Missing "data_file" or "game" parameter in request body', 400)
    }
    if (!existsSync(file)) {
      return errorJson(
        'Data file not found. Please load draws first.',
        400,
      )
    }

    // ── Parse and clamp max_runs ──────────────────────────────────────────
    let parsedMaxRuns = MAX_INDIVIDUAL_RUNS
    if (
      typeof max_runs === 'number' &&
      Number.isFinite(max_runs) &&
      max_runs > 0
    ) {
      parsedMaxRuns = Math.min(Math.floor(max_runs), MAX_INDIVIDUAL_RUNS)
    }

    // ── Clear existing state if restarting ────────────────────────────────
    if (restart) {
      const oldState = godModeStates.get(game)
      if (oldState && (oldState.status === 'running' || oldState.status === 'pending')) {
        // Cannot restart while a run is in progress
        return errorJson(
          'Cannot restart God Mode while a run is in progress. Wait for it to finish.',
          409,
        )
      }
      godModeStates.delete(game)
    }

    // ── Initialize state and start background execution ───────────────────
    const state: GodModeState = {
      status: 'pending',
      runs_completed: 0,
      runs_total: 0,
      runs_failed: 0,
      startedAt: Date.now(),
      avgRunDurationMs: undefined,
      lastRunStartedAt: undefined,
    }
    godModeStates.set(game, state)

    // v38.3.0: Register started_at for crash detection
    godModeStartedAt.set(game, state.startedAt)

    // Fire-and-forget: the background run updates state in place
    executeGodMode(game, file, parsedMaxRuns).catch((err) => {
      console.error(`[god-mode] Unhandled background error for ${game}:`, err)
      const s = godModeStates.get(game)
      if (s) {
        s.status = 'error'
        s.error = err instanceof Error ? err.message : 'Unknown background error'
      }
    })

    console.log(
      `[god-mode] ${game}: new God Mode started (max_runs=${parsedMaxRuns}, file=${file})`,
    )

    return NextResponse.json({
      status: 'pending',
      runs_completed: 0,
      runs_total: 0,
      started_at: state.startedAt,
      _refreshing: true,
      _message: 'God Mode started. Running multiple predict.py invocations with varied parameters...',
    })
  } catch (error) {
    return errorJson(
      error instanceof Error ? error.message : 'Internal server error',
      500,
    )
  }
}
