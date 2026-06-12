import { NextResponse } from 'next/server'
import { existsSync, readFileSync } from 'fs'
import { validateGameId, validateFilePath, getDrawsFilePath, getDrawRangeInfo, errorJson, safeParseStdout } from '@/lib/api-utils'
import { runPythonScript } from '@/lib/python-runner'
import { rateLimit } from '@/lib/rate-limit'

/**
 * POST /api/lottery/staged-analysis
 *
 * Runs N staged predictions where:
 * - Stage i: train on draws[1..total-N+i], predict draw[total-N+i+1]
 * - Compares prediction with actual draw data
 * - Returns detailed per-stage metrics
 *
 * Body: { game: string, n_stages: number (1-10), enable_cv?: boolean }
 */
export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { game, n_stages = 5, enable_cv = false } = body

    // Rate limit
    const rl = rateLimit(`staged-${game || 'unknown'}`, 2, 5 * 60_000)
    if (!rl.allowed) {
      return errorJson(
        `Слишком много запросов. Подождите ${Math.ceil(rl.resetIn / 1000)}с.`,
        429,
        { retry_after: Math.ceil(rl.resetIn / 1000) },
      )
    }

    const gameErr = validateGameId(game)
    if (gameErr) return errorJson(gameErr, 400)

    if (!game) {
      return errorJson('Missing "game" parameter', 400)
    }

    // Validate n_stages
    const N = Math.min(Math.max(parseInt(String(n_stages), 10) || 5, 1), 10)

    const file = getDrawsFilePath(game)
    const fileErr = validateFilePath(file)
    if (fileErr) return errorJson(fileErr, 400)

    if (!existsSync(file)) {
      return errorJson('Файл данных не найден. Сначала загрузите тиражи.', 400)
    }

    // Get draw range info
    const drawRange = getDrawRangeInfo(file)
    if (!drawRange || drawRange.total < N + 10) {
      return errorJson(
        `Недостаточно тиражей для анализа (${drawRange?.total || 0} доступно, нужно минимум ${N + 10}).`,
        400,
      )
    }

    // Read all draws to extract actual numbers for comparison
    // Note: For very large files (>100k lines), this could be memory-intensive.
    // Current max is ~13k draws for most games, which is acceptable.
    const content = readFileSync(file, 'utf-8')
    const lines = content.split('\n').filter((l: string) => l.trim() && l.includes('||'))

    // Parse draws: { drawNo: { b1: number[], b2: number[] } }
    const drawMap = new Map<number, { b1: number[]; b2: number[] }>()
    for (const line of lines) {
      const parts = line.split('||')
      if (parts.length < 3) continue
      const drawNo = parseInt(parts[1].trim(), 10)
      if (isNaN(drawNo)) continue
      const b1 = parts[2].trim().split(',').map((n: string) => parseInt(n.trim(), 10)).filter((n: number) => !isNaN(n))
      const b2 = parts.length >= 4 && parts[3].trim()
        ? parts[3].trim().split(',').map((n: string) => parseInt(n.trim(), 10)).filter((n: number) => !isNaN(n))
        : []
      drawMap.set(drawNo, { b1, b2 })
    }

    const allDrawNos = Array.from(drawMap.keys()).sort((a, b) => a - b)
    const totalDraws = allDrawNos.length
    const firstDraw = allDrawNos[0]
    const lastDraw = allDrawNos[totalDraws - 1]

    // Run staged predictions sequentially
    const stages: unknown[] = []

    for (let i = 0; i < N; i++) {
      const trainToIndex = totalDraws - N + i // 0-based index in allDrawNos
      const trainToDrawNo = allDrawNos[trainToIndex]
      const predictDrawNo = allDrawNos[trainToIndex + 1]
      const actualData = drawMap.get(predictDrawNo)

      if (!actualData) continue

      // Build args for predict.py
      const args = ['--file', file, '--no-cv', '--batch-step', '50', '--full-every', '5', '--from-draw', String(firstDraw), '--to-draw', String(trainToDrawNo)]

      try {
        const { stdout, code } = await runPythonScript('predict.py', args, { timeout: 300_000 })
        if (code !== 0 || !stdout) continue

        const parsed = safeParseStdout(stdout)
        if (!parsed?.data) continue

        const data = parsed.data as Record<string, unknown>
        const pred = data.prediction as Record<string, unknown> | undefined
        const predB1 = (pred?.block1 as number[]) || []
        const predB2 = (pred?.block2 as number[]) || []

        // Calculate hits
        const actualB1Set = new Set(actualData.b1)
        const actualB2Set = new Set(actualData.b2)
        const hitsB1 = predB1.filter(n => actualB1Set.has(n)).length
        const hitsB2 = predB2.filter(n => actualB2Set.has(n)).length

        // Extract top5 models
        const top5raw = data.top5_models as Record<string, unknown> | undefined
        const top5preds = (top5raw?.predictions as unknown[]) || []

        // Extract consensus
        const consensus = pred?.consensus_agreement_b1 as number | undefined
        const consensusB2 = pred?.consensus_agreement_b2 as number | undefined

        // Extract analysis methods count
        const methods = (data.analysis_methods as string[]) || []

        stages.push({
          stage: i + 1,
          train_from: firstDraw,
          train_to: trainToDrawNo,
          predict_draw: predictDrawNo,
          predicted_b1: predB1,
          predicted_b2: predB2,
          actual_b1: actualData.b1,
          actual_b2: actualData.b2,
          hits_b1: hitsB1,
          hits_b2: hitsB2,
          total_hits: hitsB1 + hitsB2,
          confidence_b1: consensus ?? 0,
          confidence_b2: consensusB2 ?? 0,
          methods_count: methods.length,
          top5_models: top5preds.slice(0, 5).map((p: unknown, idx: number) => {
            const m = p as Record<string, unknown>
            return {
              name: (m.name as string) || `Model ${idx + 1}`,
              b1: (m.b1 as number[]) || [],
              b2: (m.b2 as number[]) || [],
              score: (m.score as number) || 0,
            }
          }),
        })
      } catch (err) {
        console.error(`[staged-analysis] Stage ${i + 1} failed:`, err)
        // Continue to next stage
      }
    }

    // Calculate hit distribution across stages
    const hitDist: Record<string, number> = { '0': 0, '1': 0, '2': 0, '3+': 0 }
    let totalHits = 0
    for (const stage of stages) {
      const s = stage as Record<string, unknown>
      const hits = s.total_hits as number || 0
      totalHits += hits
      if (hits === 0) hitDist['0']++
      else if (hits === 1) hitDist['1']++
      else if (hits === 2) hitDist['2']++
      else hitDist['3+']++
    }

    // Calculate comparison with previous stages (improvement trend)
    const avgHits = stages.length > 0 ? (totalHits / stages.length).toFixed(2) : '0'

    // Quality estimate for next prediction
    const last3Stages = stages.slice(-3)
    const recentAvg = last3Stages.length > 0
      ? last3Stages.reduce((sum: number, s: unknown) => sum + ((s as Record<string, unknown>).total_hits as number || 0), 0) / last3Stages.length
      : 0
    const qualityEstimate = recentAvg > 0 ? recentAvg.toFixed(2) : avgHits

    return NextResponse.json({
      status: 'done',
      current_stage: stages.length,
      total_stages: N,
      stages,
      summary: {
        avg_hits: parseFloat(avgHits),
        quality_estimate: parseFloat(qualityEstimate),
        hit_distribution: hitDist,
        total_stages_completed: stages.length,
      },
    })
  } catch (error) {
    return errorJson(error instanceof Error ? error.message : 'Unknown error', 500)
  }
}
