'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Brain, Target, Zap, ArrowLeft, ArrowRight, Loader2,
  AlertTriangle, RefreshCw, TrendingUp, BarChart3, Activity,
  GitBranch, Sparkles, Gauge, Users, Database, Crosshair,
} from 'lucide-react'
import { motion } from 'framer-motion'
import type { GameAnalysis, PredictionResult, WizardStep } from './types'
import { fadeIn, fadeInInstant } from './types'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

// Extracted sub-components
import {
  TopModelsCard,
  HeatmapCard,
  PairAnalysisCard,
  GapAnalysisCard,
  NumberSpectrumCard,
  CrossGameCard,
  DrawScheduleCard,
  FrequencyAnalysisCard,
  SumRangeStatsCard,
} from './PredictionCards'

interface Step3PredictProps {
  selectedGame: GameAnalysis
  predictLoading: boolean
  predictResult: PredictionResult | null
  predictError: string | null
  enableCv: boolean
  setEnableCv: (v: boolean) => void
  activeModelCount: number | null
  predictPollSeconds?: number
  handlePredict: () => void
  setStep: (step: WizardStep) => void
}

export function Step3Predict({
  selectedGame,
  predictLoading,
  predictResult,
  predictError,
  enableCv,
  setEnableCv,
  activeModelCount,
  predictPollSeconds = 0,
  handlePredict,
  setStep,
}: Step3PredictProps) {
  const reducedMotion = usePrefersReducedMotion()
  const anim = reducedMotion ? fadeInInstant : fadeIn

  return (
    <motion.div key="step3" id="step-3" role="tabpanel" aria-labelledby="tab-3" {...anim}>
      <div className="flex items-center gap-3 mb-4">
        <Button variant="ghost" size="sm" onClick={() => setStep(2)} className="text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4 mr-1" /> Назад
        </Button>
        <h2 className="text-lg font-bold">Предсказание: {selectedGame.name}</h2>
      </div>

      {!predictResult && !predictLoading && !predictError && (
        <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
          <CardContent className="py-6 flex flex-col items-center gap-4">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center">
              <Zap className="h-8 w-8 text-white" />
            </div>
            <div className="text-center">
              <p className="text-base font-bold text-white">Запустить анализ</p>
              <p className="text-xs text-slate-400 mt-1">
                Частотный анализ + анализ разрывов + импульс + позиционный ансамбль
              </p>
            </div>
            {/* v26.0: CV toggle — disabled by default for speed */}
            <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={enableCv}
                onChange={(e) => setEnableCv(e.target.checked)}
                className="rounded border-white/20 bg-white/5 text-blue-500 focus:ring-blue-500/30"
              />
              <span>K-fold кросс-валидация <span className="text-slate-500">(медленнее, для игр &gt;500 тиражей)</span></span>
            </label>
            <Button
              onClick={handlePredict}
              className="h-12 px-8 bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-500 hover:to-indigo-400 text-white font-semibold"
            >
              <Brain className="h-5 w-5 mr-2" />
              Запустить анализ ({activeModelCount != null ? activeModelCount : 133} моделей)
            </Button>
          </CardContent>
        </Card>
      )}

      {predictLoading && (
        <Card role="status" aria-live="polite" className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="py-8 flex flex-col items-center gap-4">
            <Loader2 className="h-10 w-10 text-blue-400 animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium text-blue-300">Обучение моделей...</p>
              <p className="text-xs text-slate-400 mt-1">
                Частотный · Разрывы · Импульс · Позиционный · k-fold CV · Monte Carlo
              </p>
            </div>
            <div className="w-full max-w-xs space-y-2">
              <Progress className="h-2 bg-white/10" />
              <p className="text-[10px] text-slate-500 text-center">
                {predictPollSeconds > 0
                  ? `Прошло ${predictPollSeconds}с — модели обрабатывают данные...`
                  : 'Обычно занимает 30–120 секунд'
                }
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {predictError && (
        <Card role="status" aria-live="polite" className="border-red-500/30 bg-red-500/5">
          <CardContent className="py-6 flex flex-col items-center gap-3">
            <AlertTriangle className="h-8 w-8 text-red-400" />
            <p className="text-sm text-red-400 whitespace-pre-line">{predictError}</p>
            <Button variant="outline" size="sm" onClick={handlePredict} className="border-red-500/30 text-red-400">
              <RefreshCw className="h-4 w-4 mr-1" /> Повторить
            </Button>
          </CardContent>
        </Card>
      )}

      {predictResult && predictResult.status === 'ok' && (
        <motion.div className="space-y-4" {...anim}>
          {/* ── Data Info Card ──────────────────────────────────── */}
          {predictResult.predictionInfo && (
            <Card className="border-cyan-500/20 bg-cyan-500/5">
              <CardContent className="py-3">
                <div className="flex items-center gap-4 flex-wrap text-xs">
                  <div className="flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-cyan-400" />
                    <span className="text-slate-400">Данные:</span>
                    <span className="font-mono text-cyan-300 font-semibold">
                      {predictResult.predictionInfo.total_draws_used.toLocaleString()} тиражей
                    </span>
                    {predictResult.predictionInfo.draw_range && (
                      <span className="text-slate-500 ml-1">
                        (№ {predictResult.predictionInfo.draw_range})
                      </span>
                    )}
                  </div>
                  {predictResult.predictionInfo.next_draw_no != null && (
                    <div className="flex items-center gap-1.5">
                      <Crosshair className="h-3.5 w-3.5 text-amber-400" />
                      <span className="text-slate-400">Предсказание для тиража:</span>
                      <span className="font-mono text-amber-300 font-semibold">
                        №{predictResult.predictionInfo.next_draw_no}
                      </span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Main Prediction */}
          <Card className="border-blue-500/30 bg-gradient-to-br from-blue-500/10 via-indigo-500/5 to-transparent overflow-hidden relative">
            <div className="absolute top-0 right-0 w-40 h-40 bg-blue-500/5 rounded-full blur-3xl" />
            <CardHeader className="pb-3 relative">
              <CardTitle className="text-sm flex items-center gap-2">
                <Target className="h-4 w-4 text-blue-400" />
                Предсказание
                <Badge variant="outline" className="text-[10px] border-blue-500/30 text-blue-400 ml-auto">
                  {predictResult.game_format}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="relative space-y-4">
              {/* Block 1 */}
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 1</p>
                <div className="flex flex-wrap gap-2">
                  {predictResult.prediction.block1.map((n, i) => (
                    <motion.div
                      key={i}
                      initial={{ scale: 0, rotate: -180 }}
                      animate={{ scale: 1, rotate: 0 }}
                      transition={{ delay: i * 0.1, type: 'spring', stiffness: 200 }}
                      className="h-12 w-12 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/30"
                    >
                      <span className="text-base font-bold text-white">{n}</span>
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* Block 2 */}
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 2</p>
                <div className="flex flex-wrap gap-2">
                  {predictResult.prediction.block2.map((n, i) => (
                    <motion.div
                      key={i}
                      initial={{ scale: 0, rotate: 180 }}
                      animate={{ scale: 1, rotate: 0 }}
                      transition={{ delay: (predictResult.prediction.block1.length + i) * 0.1, type: 'spring', stiffness: 200 }}
                      className="h-12 w-12 rounded-full bg-gradient-to-br from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/30"
                    >
                      <span className="text-base font-bold text-white">{n}</span>
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* Consensus Strength */}
              {predictResult.consensus_strength && (
                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="rounded-lg bg-white/5 p-3 text-center">
                    <div className="text-[10px] text-slate-400 mb-1">Согласие Б1</div>
                    <div className="text-lg font-bold text-blue-400">
                      {predictResult.consensus_strength.block1 != null ? (predictResult.consensus_strength.block1 * 100).toFixed(1) : '—'}%
                    </div>
                  </div>
                  <div className="rounded-lg bg-white/5 p-3 text-center">
                    <div className="text-[10px] text-slate-400 mb-1">Согласие Б2</div>
                    <div className="text-lg font-bold text-emerald-400">
                      {predictResult.consensus_strength.block2 != null ? (predictResult.consensus_strength.block2 * 100).toFixed(1) : '—'}%
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Model Quality: Accuracy Card ──────────────────────── */}
          {(() => {
            const bt = predictResult.backtest as Record<string, number> | undefined
            const hasData = bt && (bt.last_50_avg != null || bt.last_100_avg != null)
            if (!hasData) return null
            const last50 = bt.last_50_avg ?? 0
            const last100 = bt.last_100_avg ?? 0
            const baseline = bt.baseline_random ?? predictResult.random_baseline?.expected_hits ?? 0
            const diff50 = last50 - baseline
            const diff100 = last100 - baseline
            const pct50 = baseline > 0 ? (diff50 / baseline) * 100 : 0
            const pct100 = baseline > 0 ? (diff100 / baseline) * 100 : 0
            const colorFor = (d: number) => d > 0.05 ? 'text-emerald-400' : d < -0.05 ? 'text-red-400' : 'text-amber-400'
            const labelFor = (d: number) => d > 0.05 ? 'Выше random' : d < -0.05 ? 'Ниже random' : '≈ random'
            return (
              <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent overflow-hidden relative">
                <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full blur-3xl" />
                <CardHeader className="pb-2 relative">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Gauge className="h-4 w-4 text-amber-400" />
                    📊 Точность моделей
                  </CardTitle>
                  <p className="text-[10px] text-slate-400">Эмпирическая точность по результатам бэктеста на исторических данных</p>
                </CardHeader>
                <CardContent className="relative">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {/* Last 50 avg */}
                    <div className="rounded-lg bg-white/5 p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-slate-400">Последние 50 тиражей</span>
                        <span className={`text-xs font-mono font-bold ${colorFor(diff50)}`}>{last50.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-500">baseline: {baseline.toFixed(2)}</span>
                        <span className={colorFor(diff50)}>
                          {diff50 >= 0 ? '+' : ''}{pct50.toFixed(1)}% · {labelFor(diff50)}
                        </span>
                      </div>
                    </div>
                    {/* Last 100 avg */}
                    <div className="rounded-lg bg-white/5 p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-slate-400">Последние 100 тиражей</span>
                        <span className={`text-xs font-mono font-bold ${colorFor(diff100)}`}>{last100.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-500">baseline: {baseline.toFixed(2)}</span>
                        <span className={colorFor(diff100)}>
                          {diff100 >= 0 ? '+' : ''}{pct100.toFixed(1)}% · {labelFor(diff100)}
                        </span>
                      </div>
                    </div>
                  </div>
                  {/* Improvement bar */}
                  {bt.improvement_pct != null && (
                    <div className="mt-3 rounded-lg bg-white/5 p-3 flex items-center gap-3">
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] text-slate-400">Превышение над случайным выбором</span>
                          <Badge variant="outline" className={`text-[10px] ${diff50 > 0 ? 'border-emerald-500/30 text-emerald-400' : diff50 < 0 ? 'border-red-500/30 text-red-400' : 'border-amber-500/30 text-amber-400'}`}>
                            {bt.improvement_pct > 0 ? '+' : ''}{bt.improvement_pct}%
                          </Badge>
                        </div>
                        <Progress value={Math.min(100, Math.max(0, 50 + (bt.improvement_pct || 0)))} className="h-1.5 bg-white/10" />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })()}

          {/* ── Model Quality: Report Card ──────────────────────────── */}
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs flex items-center gap-2">
                <Users className="h-3.5 w-3.5 text-violet-400" />
                📋 Отчёт моделей
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Models used */}
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400">Использовано моделей</span>
                <span className="font-mono text-white font-bold">{predictResult.models_used ?? '—'}</span>
              </div>
              {/* Consensus % */}
              {predictResult.consensus_strength && (
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-400">Согласие моделей</span>
                    <span className="font-mono text-violet-400">
                      {(() => {
                        const c = predictResult.consensus_strength
                        const avg = ((c.block1 ?? 0) + (c.block2 ?? 0)) / 2 * 100
                        return avg.toFixed(1) + '%'
                      })()}
                    </span>
                  </div>
                  <Progress
                    value={((predictResult.consensus_strength.block1 ?? 0) + (predictResult.consensus_strength.block2 ?? 0)) / 2 * 100}
                    className="h-1.5 bg-white/10"
                  />
                </div>
              )}
              {/* Backtest avg 50 vs baseline */}
              {(() => {
                const bt = predictResult.backtest as Record<string, number> | undefined
                if (!bt || bt.backtest_avg_50 == null) return null
                const baseline = bt.baseline_random ?? predictResult.random_baseline?.expected_hits ?? 0
                const diff = (bt.backtest_avg_50 ?? 0) - baseline
                const clr = diff > 0.05 ? 'text-emerald-400' : diff < -0.05 ? 'text-red-400' : 'text-amber-400'
                return (
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-400">Бэктест avg (50)</span>
                    <span className={`font-mono ${clr}`}>
                      {bt.backtest_avg_50?.toFixed(2)}
                      <span className="text-[10px] text-slate-500 ml-1">
                        (baseline {baseline.toFixed(2)})
                      </span>
                    </span>
                  </div>
                )
              })()}
            </CardContent>
          </Card>

          {/* Next Draw Info */}
          <DrawScheduleCard predictResult={predictResult} />

          {/* Accuracy Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Backtest with Heatmap */}
            {predictResult.backtest && ('last_50_avg' in (predictResult.backtest as Record<string, unknown>) || 'heatmap' in (predictResult.backtest as Record<string, unknown>)) && (
              <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs flex items-center gap-2">
                    <TrendingUp className="h-3.5 w-3.5 text-amber-400" />
                    Бэктест (последние тиражи)
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {(['50', '100', '200'] as const).map((n) => {
                    const key = `last_${n}_avg` as const
                    const val = (predictResult.backtest as Record<string, number>)[key]
                    const baseline = (predictResult.backtest as Record<string, number>)['baseline_random']
                    const color = val != null && baseline != null && val > baseline ? 'text-emerald-400' : 'text-white'
                    return (
                      <div key={n} className="flex justify-between items-center text-xs">
                        <span className="text-slate-400">Последние {n}</span>
                        <span className={`font-mono ${color}`}>{val != null ? val.toFixed(2) : '—'}</span>
                      </div>
                    )
                  })}
                  {(predictResult.backtest as Record<string, number>)['improvement_pct'] !== undefined && (
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-400">Превышение baseline</span>
                      <span className="font-mono text-amber-400">+{(predictResult.backtest as Record<string, number>)['improvement_pct']}%</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Expanded Heatmap */}
            <HeatmapCard predictResult={predictResult} />
          </div>

          {/* Frequency Analysis */}
          <FrequencyAnalysisCard predictResult={predictResult} />

          {/* Top 5 Best Models */}
          <TopModelsCard predictResult={predictResult} />

          {/* Number Spectrum */}
          <NumberSpectrumCard predictResult={predictResult} />

          {/* Cross Validation */}
          {predictResult.cross_validation && 'avg_hits' in (predictResult.cross_validation as Record<string, unknown>) && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <BarChart3 className="h-3.5 w-3.5 text-violet-400" />
                  K-Fold кросс-валидация
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {(() => {
                  const cv = predictResult.cross_validation as Record<string, unknown>
                  return (
                    <>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Средняя точность</span>
                        <span className="font-mono text-white">{(cv.avg_hits as number)?.toFixed(3) ?? '—'}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Макс. попаданий</span>
                        <span className="font-mono text-white">{(cv.max_hits as number) ?? '—'}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Folds</span>
                        <span className="font-mono text-slate-300">{cv.folds ?? '—'}</span>
                      </div>
                    </>
                  )
                })()}
              </CardContent>
            </Card>
          )}

          {/* Monte Carlo + Random Baseline */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {predictResult.monte_carlo && 'expected_hits' in (predictResult.monte_carlo as Record<string, unknown>) && (
              <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs flex items-center gap-2">
                    <Activity className="h-3.5 w-3.5 text-cyan-400" />
                    Monte Carlo ({(predictResult.monte_carlo as Record<string, number>)?.iterations || 5000} итер.)
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Ожид. попаданий</span>
                    <span className="font-mono text-white">{(predictResult.monte_carlo as Record<string, number>).expected_hits?.toFixed(3)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">95% CI</span>
                    <span className="font-mono text-slate-300">
                      [{(predictResult.monte_carlo as Record<string, number>).ci_95_low}, {(predictResult.monte_carlo as Record<string, number>).ci_95_high}]
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">P(≥5 попаданий)</span>
                    <span className="font-mono text-amber-400">{(((predictResult.monte_carlo as Record<string, number>).p_ge_5 ?? 0) * 100).toFixed(1)}%</span>
                  </div>
                </CardContent>
              </Card>
            )}

            {predictResult.random_baseline && predictResult.random_baseline.expected_hits > 0 && (
              <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs flex items-center gap-2">
                    <Sparkles className="h-3.5 w-3.5 text-slate-400" />
                    Случайный baseline
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Ожид. попаданий</span>
                    <span className="font-mono text-slate-300">{predictResult.random_baseline.expected_hits?.toFixed(2)}</span>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Pair Analysis */}
          <PairAnalysisCard predictResult={predictResult} />

          {/* Gap Analysis */}
          <GapAnalysisCard predictResult={predictResult} />

          {/* Method Breakdown */}
          {predictResult.analysis_methods && predictResult.analysis_methods.length > 0 && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <GitBranch className="h-3.5 w-3.5 text-blue-400" />
                  Разбивка по моделям
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {predictResult.analysis_methods.map((method, i) => (
                    <div key={i} className="flex items-center gap-3 text-xs">
                      <Badge variant="outline" className="text-[10px] border-white/10 text-slate-400 shrink-0 w-24 justify-center">
                        #{i + 1}
                      </Badge>
                      <span className="text-slate-300 truncate">{method}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Sum/Range Statistics */}
          <SumRangeStatsCard predictResult={predictResult} />

          {/* Cross-Game Analysis */}
          <CrossGameCard predictResult={predictResult} />
        </motion.div>
      )}
    </motion.div>
  )
}
