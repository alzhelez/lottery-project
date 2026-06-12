'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  ArrowLeft, Loader2, AlertTriangle, RefreshCw, FlaskConical,
  Target, TrendingUp, BarChart3, Activity,
} from 'lucide-react'
import { motion } from 'framer-motion'
import type { GameAnalysis, DrawRangeInfo, StagedAnalysisResult, WizardStep, PredictionResult } from './types'
import { fadeIn, fadeInInstant } from './types'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { useState, useCallback } from 'react'

interface StagedAnalysisProps {
  selectedGame: GameAnalysis
  drawRange: DrawRangeInfo | null
  predictResult: PredictionResult | null
  stagingLoading: boolean
  stagingResult: StagedAnalysisResult | null
  stagingError: string | null
  onRunStaging: (nStages: number) => void
  setStep: (step: WizardStep) => void
}

export function StagedAnalysis({
  selectedGame,
  drawRange,
  predictResult,
  stagingLoading,
  stagingResult,
  stagingError,
  onRunStaging,
  setStep,
}: StagedAnalysisProps) {
  const reducedMotion = usePrefersReducedMotion()
  const anim = reducedMotion ? fadeInInstant : fadeIn
  const [nStages, setNStages] = useState(5)

  const handleRun = useCallback(() => {
    onRunStaging(nStages)
  }, [nStages, onRunStaging])

  return (
    <motion.div key="step4-staged" id="step-4" role="tabpanel" aria-labelledby="tab-4" {...anim}>
      <div className="flex items-center gap-3 mb-4">
        <Button variant="ghost" size="sm" onClick={() => setStep(3)} className="text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4 mr-1" /> Назад
        </Button>
        <h2 className="text-lg font-bold">Поэтапный анализ</h2>
      </div>

      {!stagingResult && !stagingLoading && !stagingError && (
        <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
          <CardContent className="py-6 flex flex-col items-center gap-4">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
              <FlaskConical className="h-8 w-8 text-white" />
            </div>
            <div className="text-center">
              <p className="text-base font-bold text-white">Поэтапный анализ</p>
              <p className="text-xs text-slate-400 mt-1">
                Итеративное обучение с проверкой на реальных данных. N последних тиражей анализируются последовательно.
              </p>
            </div>

            {/* N stages selector */}
            <div className="flex items-center gap-3">
              <label className="text-xs text-slate-400">Количество этапов:</label>
              <div className="flex gap-1">
                {[3, 5, 7, 10].map(n => (
                  <Button
                    key={n}
                    size="sm"
                    variant="outline"
                    onClick={() => setNStages(n)}
                    className={
                      nStages === n
                        ? 'bg-amber-500/20 text-amber-400 border-amber-500/30 hover:bg-amber-500/30'
                        : 'bg-white/5 text-slate-400 border-white/10 hover:bg-white/10'
                    }
                  >
                    {n}
                  </Button>
                ))}
              </div>
            </div>

            {drawRange && (
              <div className="text-[11px] text-slate-500 text-center">
                Доступно {drawRange.total} тиражей ({drawRange.first}–{drawRange.last}).
                Каждый этап обучается на {Math.max(1, drawRange.total - nStages)}+ тиражей и проверяется на следующем.
              </div>
            )}

            {!drawRange && (
              <div className="text-[11px] text-slate-500 text-center">
                Сначала загрузите тиражи (шаг 2) и выполните прогноз (шаг 3).
              </div>
            )}

            <Button
              onClick={handleRun}
              disabled={stagingLoading || !drawRange || !predictResult}
              className="h-12 px-8 bg-gradient-to-r from-amber-600 to-orange-500 hover:from-amber-500 hover:to-orange-400 text-white font-semibold disabled:opacity-50"
            >
              <FlaskConical className="h-5 w-5 mr-2" />
              Запустить ({nStages} этапов)
            </Button>
          </CardContent>
        </Card>
      )}

      {stagingLoading && (
        <Card role="status" aria-live="polite" className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="py-8 flex flex-col items-center gap-4">
            <Loader2 className="h-10 w-10 text-amber-400 animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium text-amber-300">Выполняется поэтапный анализ...</p>
              <p className="text-xs text-slate-400 mt-1">
                Каждый этап: обучение на доступных тиражах → прогноз → сравнение с реальными данными
              </p>
            </div>
            <div className="w-full max-w-xs space-y-2">
              <Progress className="h-2 bg-white/10" />
              <p className="text-[10px] text-slate-500 text-center">
                Это может занять несколько минут ({nStages} × прогноз)
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {stagingError && (
        <Card role="status" aria-live="polite" className="border-red-500/30 bg-red-500/5">
          <CardContent className="py-6 flex flex-col items-center gap-3">
            <AlertTriangle className="h-8 w-8 text-red-400" />
            <p className="text-sm text-red-400 whitespace-pre-line">{stagingError}</p>
            <Button variant="outline" size="sm" onClick={handleRun} className="border-red-500/30 text-red-400">
              <RefreshCw className="h-4 w-4 mr-1" /> Повторить
            </Button>
          </CardContent>
        </Card>
      )}

      {stagingResult && stagingResult.status === 'done' && (
        <motion.div className="space-y-4" {...anim}>
          {/* Summary Card */}
          <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent overflow-hidden relative">
            <div className="absolute top-0 right-0 w-40 h-40 bg-amber-500/5 rounded-full blur-3xl" />
            <CardHeader className="pb-3 relative">
              <CardTitle className="text-sm flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-amber-400" />
                Результат поэтапного анализа
                <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400 ml-auto">
                  {stagingResult.stages.length}/{stagingResult.total_stages} этапов
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="relative">
              {stagingResult.summary && (
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="rounded-lg bg-white/5 p-3 text-center">
                    <div className="text-[10px] text-slate-400 mb-1">Ср. попаданий</div>
                    <div className="text-lg font-bold text-amber-400">
                      {(stagingResult.summary.avg_hits ?? 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-white/5 p-3 text-center">
                    <div className="text-[10px] text-slate-400 mb-1">Оценка качества</div>
                    <div className="text-lg font-bold text-blue-400">
                      {(stagingResult.summary.quality_estimate ?? 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-white/5 p-3 text-center">
                    <div className="text-[10px] text-slate-400 mb-1">Этапов</div>
                    <div className="text-lg font-bold text-white">
                      {stagingResult.summary.total_stages_completed}
                    </div>
                  </div>
                </div>
              )}

              {/* Hit Distribution */}
              {stagingResult.summary?.hit_distribution && (
                <div className="space-y-2">
                  <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Распределение попаданий</p>
                  <div className="flex gap-2">
                    {Object.entries(stagingResult.summary.hit_distribution).map(([label, count]) => {
                      const total = Object.values(stagingResult.summary.hit_distribution).reduce((a: number, b: number) => a + b, 0) || 1
                      const pct = ((count as number) / total * 100).toFixed(0)
                      const color = label === '0' ? 'bg-red-500/30 text-red-400'
                        : label === '1' ? 'bg-amber-500/30 text-amber-400'
                        : label === '2' ? 'bg-emerald-500/30 text-emerald-400'
                        : 'bg-blue-500/30 text-blue-400'
                      return (
                        <div key={label} className="flex-1 rounded-lg bg-white/5 p-2 text-center">
                          <div className="text-xs font-bold text-white">{label} попад.</div>
                          <div className="text-lg font-bold">{count as number}</div>
                          <div className={`text-[9px] px-1.5 py-0.5 rounded-full inline-block mt-1 ${color}`}>
                            {pct}%
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Stage-by-Stage Table */}
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs flex items-center gap-2">
                <BarChart3 className="h-3.5 w-3.5 text-amber-400" />
                Детализация по этапам
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto max-h-96 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[#0a0f1e] z-10">
                    <tr className="text-slate-400 border-b border-white/10">
                      <th className="py-2 px-2 text-left font-medium">#</th>
                      <th className="py-2 px-2 text-left font-medium">Обучение</th>
                      <th className="py-2 px-2 text-left font-medium">Тираж</th>
                      <th className="py-2 px-2 text-left font-medium">Прогноз</th>
                      <th className="py-2 px-2 text-left font-medium">Реально</th>
                      <th className="py-2 px-2 text-center font-medium">Б1</th>
                      <th className="py-2 px-2 text-center font-medium">Б2</th>
                      <th className="py-2 px-2 text-center font-medium">Итого</th>
                      <th className="py-2 px-2 text-center font-medium">Доверие</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stagingResult.stages.map((stage, idx) => {
                      const s = stage as Record<string, unknown>
                      const hits = (s.total_hits as number) || 0
                      const prevHits = idx > 0 ? ((stagingResult.stages[idx - 1] as Record<string, unknown>).total_hits as number) || 0 : null
                      const trend = prevHits !== null
                        ? hits > prevHits ? '↑' : hits < prevHits ? '↓' : '→'
                        : ''
                      const trendColor = trend === '↑' ? 'text-emerald-400' : trend === '↓' ? 'text-red-400' : 'text-slate-500'

                      return (
                        <tr key={s.stage as number} className="border-b border-white/5 hover:bg-white/[0.02]">
                          <td className="py-2 px-2">
                            <Badge variant="outline" className="text-[9px] border-white/10 text-slate-400">
                              {s.stage as number}
                            </Badge>
                          </td>
                          <td className="py-2 px-2 text-slate-400 font-mono">
                            {s.train_from as number}–{s.train_to as number}
                          </td>
                          <td className="py-2 px-2 text-white font-mono font-bold">
                            #{s.predict_draw as number}
                          </td>
                          <td className="py-2 px-2">
                            <div className="flex flex-wrap gap-0.5">
                              {((s.predicted_b1 as number[]) || []).slice(0, 4).map((n: number, i: number) => (
                                <span key={`pb1-${i}`} className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-blue-500/15 text-blue-300">
                                  {n}
                                </span>
                              ))}
                              {((s.predicted_b1 as number[]) || []).length > 4 && (
                                <span className="text-slate-500">+{((s.predicted_b1 as number[]) || []).length - 4}</span>
                              )}
                            </div>
                          </td>
                          <td className="py-2 px-2">
                            <div className="flex flex-wrap gap-0.5">
                              {((s.actual_b1 as number[]) || []).slice(0, 4).map((n: number, i: number) => {
                                const isHit = ((s.predicted_b1 as number[]) || []).includes(n)
                                return (
                                  <span key={`ab1-${i}`} className={`inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono ${isHit ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/5 text-slate-400'}`}>
                                    {n}
                                  </span>
                                )
                              })}
                            </div>
                          </td>
                          <td className="py-2 px-2 text-center">
                            <span className={`font-mono font-bold ${(s.hits_b1 as number) > 0 ? 'text-emerald-400' : 'text-slate-500'}`}>
                              {s.hits_b1 as number}
                            </span>
                          </td>
                          <td className="py-2 px-2 text-center">
                            <span className={`font-mono font-bold ${(s.hits_b2 as number) > 0 ? 'text-emerald-400' : 'text-slate-500'}`}>
                              {s.hits_b2 as number}
                            </span>
                          </td>
                          <td className="py-2 px-2 text-center">
                            <span className={`font-mono font-bold text-base ${hits >= 3 ? 'text-emerald-400' : hits >= 1 ? 'text-amber-400' : 'text-slate-500'}`}>
                              {hits}
                            </span>
                            <span className={`text-[9px] ml-1 ${trendColor}`}>{trend}</span>
                          </td>
                          <td className="py-2 px-2 text-center">
                            <span className="text-[10px] text-slate-400 font-mono">
                              {((s.confidence_b1 as number) * 100).toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Comparison with basic prediction (Step 3) */}
          {predictResult && predictResult.status === 'ok' && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <Target className="h-3.5 w-3.5 text-violet-400" />
                  Оценка качества финального прогноза
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-white/5 p-3">
                  <p className="text-[10px] text-slate-400 mb-2">
                    Среднее попаданий за {stagingResult.stages.length} этапов — это оценка ожидаемой точности прогноза на следующий тираж.
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="text-center">
                      <p className="text-[10px] text-slate-500">Поэтапный анализ</p>
                      <p className="text-sm font-bold text-amber-400 font-mono">
                        {(stagingResult.summary?.quality_estimate ?? 0).toFixed(2)} ср. попад.
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-[10px] text-slate-500">Случайный baseline</p>
                      <p className="text-sm font-bold text-slate-400 font-mono">
                        {predictResult.random_baseline?.expected_hits?.toFixed(2) ?? '—'} ожид.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Trend assessment */}
                {stagingResult.stages.length >= 3 && (() => {
                  const last3 = stagingResult.stages.slice(-3)
                  const avg1 = (last3[0] as Record<string, unknown>).total_hits as number || 0
                  const avg2 = (last3[1] as Record<string, unknown>).total_hits as number || 0
                  const avg3 = (last3[2] as Record<string, unknown>).total_hits as number || 0
                  const improving = avg3 > avg1
                  const stable = Math.abs(avg3 - avg1) <= 1
                  let verdict = 'Модель показывает стабильный результат'
                  let verdictColor = 'text-slate-400'
                  if (improving && !stable) { verdict = 'Модель улучшается на последних этапах'; verdictColor = 'text-emerald-400' }
                  else if (!improving && !stable) { verdict = 'Модель показывает тенденцию к снижению'; verdictColor = 'text-red-400' }
                  return (
                    <div className={`text-[11px] flex items-center gap-2 ${verdictColor}`}>
                      {improving ? <TrendingUp className="h-3.5 w-3.5" /> : <Activity className="h-3.5 w-3.5" />}
                      {verdict}
                    </div>
                  )
                })()}
              </CardContent>
            </Card>
          )}

          {/* Re-run button */}
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              onClick={() => onRunStaging(nStages)}
              className="border-white/10 text-slate-400 hover:text-white"
            >
              <RefreshCw className="h-4 w-4 mr-1" /> Запустить снова ({nStages} этапов)
            </Button>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
