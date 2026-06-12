'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  ArrowLeft, Loader2, AlertTriangle, RefreshCw, Layers, Target,
  Eye, BarChart3, Shield, GitBranch,
} from 'lucide-react'
import { motion } from 'framer-motion'
import type { GameAnalysis, PredictionResult, PipelineResult, WizardStep } from './types'
import { BLOCK_COLOR_CLASSES, fadeIn, fadeInInstant } from './types'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

interface Step4PipelineProps {
  selectedGame: GameAnalysis
  pipelineLoading: boolean
  pipelineResult: PipelineResult | null
  pipelineError: string | null
  predictResult: PredictionResult | null
  handlePipeline: () => void
  setStep: (step: WizardStep) => void
}

export function Step4Pipeline({
  selectedGame,
  pipelineLoading,
  pipelineResult,
  pipelineError,
  predictResult,
  handlePipeline,
  setStep,
}: Step4PipelineProps) {
  const reducedMotion = usePrefersReducedMotion()
  const anim = reducedMotion ? fadeInInstant : fadeIn

  return (
    <motion.div key="step4" id="step-4" role="tabpanel" aria-labelledby="tab-4" {...anim}>
      <div className="flex items-center gap-3 mb-4">
        <Button variant="ghost" size="sm" onClick={() => setStep(3)} className="text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4 mr-1" /> Назад
        </Button>
        <h2 className="text-lg font-bold">Pipeline позиционного анализа</h2>
      </div>

      {!pipelineResult && !pipelineLoading && !pipelineError && (
        <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
          <CardContent className="py-6 flex flex-col items-center gap-4">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
              <Layers className="h-8 w-8 text-white" />
            </div>
            <div className="text-center">
              <p className="text-base font-bold text-white">Pipeline усреднения</p>
              <p className="text-xs text-slate-400 mt-1">
                Позиционный ансамбль → взвешенное голосование по позициям
              </p>
            </div>
            <Button
              onClick={handlePipeline}
              className="h-12 px-8 bg-gradient-to-r from-violet-600 to-purple-500 hover:from-violet-500 hover:to-purple-400 text-white font-semibold"
            >
              <Layers className="h-5 w-5 mr-2" />
              Запустить Pipeline
            </Button>
          </CardContent>
        </Card>
      )}

      {pipelineLoading && (
        <Card role="status" aria-live="polite" className="border-violet-500/30 bg-violet-500/5">
          <CardContent className="py-8 flex flex-col items-center gap-4">
            <Loader2 className="h-10 w-10 text-violet-400 animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium text-violet-300">Анализ позиций...</p>
              <p className="text-xs text-slate-400 mt-1">
                Взвешенное голосование моделей по позициям
              </p>
            </div>
            <div className="w-full max-w-xs">
              <Progress className="h-2 bg-white/10" />
            </div>
          </CardContent>
        </Card>
      )}

      {pipelineError && (
        <Card role="status" aria-live="polite" className="border-red-500/30 bg-red-500/5">
          <CardContent className="py-6 flex flex-col items-center gap-3">
            <AlertTriangle className="h-8 w-8 text-red-400" />
            <p className="text-sm text-red-400 whitespace-pre-line">{pipelineError}</p>
            <Button variant="outline" size="sm" onClick={handlePipeline} className="border-red-500/30 text-red-400">
              <RefreshCw className="h-4 w-4 mr-1" /> Повторить
            </Button>
          </CardContent>
        </Card>
      )}

      {pipelineResult && pipelineResult.status === 'ok' && (
        <motion.div className="space-y-4" {...anim}>
          {/* Final Pipeline Prediction */}
          <Card className="border-violet-500/30 bg-gradient-to-br from-violet-500/10 via-purple-500/5 to-transparent overflow-hidden relative">
            <div className="absolute top-0 right-0 w-40 h-40 bg-violet-500/5 rounded-full blur-3xl" />
            <CardHeader className="pb-3 relative">
              <CardTitle className="text-sm flex items-center gap-2">
                <Target className="h-4 w-4 text-violet-400" />
                Финальное предсказание (Pipeline)
                <Badge variant="outline" className="text-[10px] border-violet-500/30 text-violet-400 ml-auto">
                  {pipelineResult.runs_performed} прогонов
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="relative space-y-4">
              {/* Block 1 */}
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 1 (Pipeline)</p>
                <div className="flex flex-wrap gap-2">
                  {pipelineResult.prediction.block1.map((n, i) => (
                    <motion.div
                      key={i}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: i * 0.08, type: 'spring' }}
                      className="h-12 w-12 rounded-full bg-gradient-to-br from-violet-500 to-purple-400 flex items-center justify-center shadow-lg shadow-violet-500/30"
                    >
                      <span className="text-base font-bold text-white">{n}</span>
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* Block 2 */}
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 2 (Pipeline)</p>
                <div className="flex flex-wrap gap-2">
                  {pipelineResult.prediction.block2.map((n, i) => (
                    <motion.div
                      key={i}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: (pipelineResult.prediction.block1.length + i) * 0.08, type: 'spring' }}
                      className="h-12 w-12 rounded-full bg-gradient-to-br from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/30"
                    >
                      <span className="text-base font-bold text-white">{n}</span>
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* Confidence */}
              <div className="grid grid-cols-3 gap-3 pt-2">
                <div className="rounded-lg bg-white/5 p-3 text-center">
                  <div className="text-[10px] text-slate-400 mb-1">Б1 доверие</div>
                  <div className="text-lg font-bold text-blue-400">
                    {Math.round(pipelineResult.confidence.block1 * 100)}%
                  </div>
                </div>
                <div className="rounded-lg bg-white/5 p-3 text-center">
                  <div className="text-[10px] text-slate-400 mb-1">Б2 доверие</div>
                  <div className="text-lg font-bold text-emerald-400">
                    {Math.round(pipelineResult.confidence.block2 * 100)}%
                  </div>
                </div>
                <div className="rounded-lg bg-white/5 p-3 text-center">
                  <div className="text-[10px] text-slate-400 mb-1">Общее</div>
                  <div className="text-lg font-bold text-violet-400">
                    {Math.round(pipelineResult.confidence.overall * 100)}%
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Block 1: Position-based prediction */}
          {pipelineResult.block1_position && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <Eye className="h-3.5 w-3.5 text-cyan-400" />
                  Блок 1: Позиционный анализ
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  {(pipelineResult.block1_position.prediction || []).map((n, i) => (
                    <span key={i} className="inline-flex items-center h-6 min-w-6 px-1.5 justify-center rounded-full text-[11px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                      {n}
                    </span>
                  ))}
                </div>
                {pipelineResult.block1_position.confidence != null && (
                  <p className="text-[10px] text-slate-400">Доверие: <span className="text-cyan-400 font-bold">{Math.round(pipelineResult.block1_position.confidence * 100)}%</span></p>
                )}
                {pipelineResult.block1_position.details && (
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {Object.entries(pipelineResult.block1_position.details).map(([posKey, posData]) => {
                      const sortedVotes = Object.entries(posData.votes).sort(([,a], [,b]) => b - a)
                      return (
                        <div key={posKey} className="flex items-center gap-2 text-xs">
                          <Badge variant="outline" className="text-[9px] border-white/10 text-slate-500 shrink-0 w-7 justify-center">
                            P{posKey}
                          </Badge>
                          <span className="inline-flex items-center h-6 min-w-6 justify-center rounded-full text-[11px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/20">
                            {posData.selected}
                          </span>
                          {sortedVotes.length > 1 && (
                            <div className="flex gap-0.5 ml-1">
                              {sortedVotes.slice(1, 4).map(([num, score]) => (
                                <span key={num} className="text-[9px] text-slate-500 font-mono">{num}({score.toFixed(1)})</span>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Block 2: Frequency-based prediction */}
          {pipelineResult.block2_frequency && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <BarChart3 className="h-3.5 w-3.5 text-emerald-400" />
                  Блок 2: Частотный анализ
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  {(pipelineResult.block2_frequency.prediction || []).map((n, i) => (
                    <span key={i} className="inline-flex items-center h-6 min-w-6 px-1.5 justify-center rounded-full text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      {n}
                    </span>
                  ))}
                </div>
                {pipelineResult.block2_frequency.details && pipelineResult.block2_frequency.details.length > 0 && (
                  <div className="space-y-0.5 max-h-48 overflow-y-auto">
                    {pipelineResult.block2_frequency.details.map((item) => (
                      <div key={item.number} className="flex items-center gap-2 text-[10px]">
                        <span className={`w-5 h-5 rounded text-[9px] font-mono flex items-center justify-center ${item.last_seen <= 3 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/5 text-slate-400'}`}>
                          {item.number}
                        </span>
                        <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                          <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.min(item.count * 2, 100)}%` }} />
                        </div>
                        <span className="font-mono text-slate-400 w-8 text-right">{item.count}×</span>
                        {item.last_seen <= 3 && <span className="text-[9px] text-emerald-400">недавно</span>}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Block 1: Frequency-based prediction */}
          {pipelineResult.block1_frequency && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <BarChart3 className="h-3.5 w-3.5 text-cyan-400" />
                  Блок 1: Частотный анализ
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  {(pipelineResult.block1_frequency.prediction || []).map((n, i) => (
                    <span key={i} className="inline-flex items-center h-6 min-w-6 px-1.5 justify-center rounded-full text-[11px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                      {n}
                    </span>
                  ))}
                </div>
                {pipelineResult.block1_frequency.details && pipelineResult.block1_frequency.details.length > 0 && (
                  <div className="space-y-0.5 max-h-48 overflow-y-auto">
                    {pipelineResult.block1_frequency.details.map((item) => (
                      <div key={item.number} className="flex items-center gap-2 text-[10px]">
                        <span className={`w-5 h-5 rounded text-[9px] font-mono flex items-center justify-center ${item.last_seen <= 3 ? 'bg-cyan-500/20 text-cyan-300' : 'bg-white/5 text-slate-400'}`}>
                          {item.number}
                        </span>
                        <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                          <div className="h-full rounded-full bg-cyan-500" style={{ width: `${Math.min(item.count * 2, 100)}%` }} />
                        </div>
                        <span className="font-mono text-slate-400 w-8 text-right">{item.count}×</span>
                        {item.last_seen <= 3 && <span className="text-[9px] text-cyan-400">недавно</span>}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Block 2: Position-based prediction */}
          {pipelineResult.block2_position && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <Eye className="h-3.5 w-3.5 text-emerald-400" />
                  Блок 2: Позиционный анализ
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  {(pipelineResult.block2_position.prediction || []).map((n, i) => (
                    <span key={i} className="inline-flex items-center h-6 min-w-6 px-1.5 justify-center rounded-full text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      {n}
                    </span>
                  ))}
                </div>
                {pipelineResult.block2_position.confidence != null && (
                  <p className="text-[10px] text-slate-400">Доверие: <span className="text-emerald-400 font-bold">{Math.round(pipelineResult.block2_position.confidence * 100)}%</span></p>
                )}
                {pipelineResult.block2_position.details && (
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {Object.entries(pipelineResult.block2_position.details).map(([posKey, posData]) => {
                      const sortedVotes = Object.entries(posData.votes).sort(([,a], [,b]) => b - a)
                      return (
                        <div key={posKey} className="flex items-center gap-2 text-xs">
                          <Badge variant="outline" className="text-[9px] border-white/10 text-slate-500 shrink-0 w-7 justify-center">
                            P{posKey}
                          </Badge>
                          <span className="inline-flex items-center h-6 min-w-6 justify-center rounded-full text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/20">
                            {posData.selected}
                          </span>
                          {sortedVotes.length > 1 && (
                            <div className="flex gap-0.5 ml-1">
                              {sortedVotes.slice(1, 4).map(([num, score]) => (
                                <span key={num} className="text-[9px] text-slate-500 font-mono">{num}({score.toFixed(1)})</span>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Top 3 Models */}
          {pipelineResult.top3_models && pipelineResult.top3_models.models && pipelineResult.top3_models.models.length > 0 && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <Shield className="h-3.5 w-3.5 text-violet-400" />
                  Топ-3 моделей Pipeline
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {pipelineResult.top3_models.models.map((model, i) => (
                  <div key={model.id} className="rounded-lg bg-white/5 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] border-violet-500/30 text-violet-400">
                          #{i + 1}
                        </Badge>
                        <span className="text-xs font-medium text-slate-300">{model.name}</span>
                      </div>
                      <span className="text-[10px] font-mono text-emerald-400">{model.avg_hits?.toFixed(2)} попад.</span>
                    </div>
                    <div className="flex gap-1.5">
                      {model.b1.map((n, j) => (
                        <span key={`b1-${j}`} className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-blue-500/15 text-blue-300">{n}</span>
                      ))}
                      {model.b2.length > 0 && <span className="text-slate-600 mx-0.5">+</span>}
                      {model.b2.map((n, j) => (
                        <span key={`b2-${j}`} className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-emerald-500/15 text-emerald-300">{n}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Comparison with Basic Prediction */}
          {predictResult && predictResult.status === 'ok' && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <BarChart3 className="h-3.5 w-3.5 text-amber-400" />
                  Сравнение: базовый прогноз vs Pipeline
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(['block1', 'block2'] as const).map((block) => {
                  const basicNums = new Set(predictResult.prediction[block])
                  const pipeNums = new Set(pipelineResult.prediction[block])
                  const consensus: number[] = []
                  const onlyBasic: number[] = []
                  const onlyPipeline: number[] = []
                  basicNums.forEach(n => {
                    if (pipeNums.has(n)) consensus.push(n)
                    else onlyBasic.push(n)
                  })
                  pipeNums.forEach(n => {
                    if (!basicNums.has(n)) onlyPipeline.push(n)
                  })
                  const label = block === 'block1' ? 'Блок 1' : 'Блок 2'
                  return (
                    <div key={block}>
                      <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">{label}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {consensus.length > 0 && consensus.sort((a, b) => a - b).map(n => (
                          <span key={`c-${n}`} className="inline-flex items-center h-6 min-w-6 px-1.5 justify-center rounded-full text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                            {n}
                          </span>
                        ))}
                        {onlyBasic.length > 0 && onlyBasic.sort((a, b) => a - b).map(n => (
                          <span key={`b-${n}`} className="inline-flex items-center h-6 min-w-6 px-1.5 justify-center rounded-full text-[11px] font-mono font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                            {n}
                          </span>
                        ))}
                        {onlyPipeline.length > 0 && onlyPipeline.sort((a, b) => a - b).map(n => (
                          <span key={`p-${n}`} className="inline-flex items-center h-6 min-w-6 px-1.5 justify-center rounded-full text-[11px] font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                            {n}
                          </span>
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-3 mt-1.5 text-[9px] text-slate-500">
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500/40" /> Совпадение ({consensus.length})</span>
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500/40" /> Только базовый ({onlyBasic.length})</span>
                        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-purple-500/40" /> Только Pipeline ({onlyPipeline.length})</span>
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          )}

          {/* v26.2: Pipeline Number Spectrum — all numbers with vote scores */}
          {pipelineResult.number_spectrum && (pipelineResult.number_spectrum.block1?.length > 0 || pipelineResult.number_spectrum.block2?.length > 0) && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <Layers className="h-3.5 w-3.5 text-violet-400" />
                  Полный спектр чисел Pipeline (голоса моделей)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(['block1', 'block2'] as const).map(block => {
                  const nums = pipelineResult.number_spectrum?.[block]
                  if (!nums || nums.length === 0) return null
                  const label = block === 'block1' ? 'Блок 1' : 'Блок 2'
                  const color = block === 'block1' ? 'blue' : 'emerald'
                  const predSet = new Set(pipelineResult.prediction[block])
                  const maxVotes = Math.max(...nums.map(n => n.votes), 1)
                  return (
                    <div key={block}>
                      <div className="flex items-center justify-between mb-1.5">
                        <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">{label}</p>
                        <span className="text-[9px] text-slate-500">{nums.length} чисел</span>
                      </div>
                      <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
                        {nums.map(item => {
                          const isPredicted = predSet.has(item.number)
                          return (
                            <div key={item.number} className={`inline-flex flex-col items-center rounded-md px-1.5 py-1 min-w-[32px] ${isPredicted ? `${BLOCK_COLOR_CLASSES[color]?.bg || ''} border ${BLOCK_COLOR_CLASSES[color]?.border || ''}` : 'bg-white/[0.03] border border-white/5'}`}>
                              <span className={`text-[10px] font-mono font-bold ${isPredicted ? (BLOCK_COLOR_CLASSES[color]?.text || 'text-slate-400') : 'text-slate-400'}`}>{item.number}</span>
                              <span className="text-[8px] text-slate-500">{item.votes}</span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
                <div className="flex gap-3 text-[9px] text-slate-500 pt-1 border-t border-white/5">
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500/40" /> В прогнозе (Б1)</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500/40" /> В прогнозе (Б2)</span>
                  <span className="text-slate-600">Число = суммарные голоса моделей</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Position Analysis (legacy) */}
          {(pipelineResult.position_analysis?.block1 && Object.keys(pipelineResult.position_analysis.block1).length > 0) && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <Eye className="h-3.5 w-3.5 text-cyan-400" />
                  Позиционный анализ (детали)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(['block1', 'block2'] as const).map((block) => {
                  const positions = pipelineResult.position_analysis[block]
                  if (!positions || Object.keys(positions).length === 0) return null
                  const label = block === 'block1' ? 'Блок 1' : 'Блок 2'
                  const color = block === 'block1' ? 'blue' : 'emerald'
                  return (
                    <div key={block}>
                      <p className="text-[10px] text-slate-400 mb-1 font-medium uppercase tracking-wider">{label}</p>
                      <div className="space-y-1">
                        {Object.entries(positions).slice(0, 8).map(([posKey, posData]) => {
                          const pd = posData as Record<string, unknown>
                          const selected = pd.selected as number | undefined
                          const votes = pd.votes as Record<string, number> | undefined
                          if (selected === undefined) return null
                          const sortedVotes = votes ? Object.entries(votes).sort(([,a], [,b]) => b - a) : []
                          return (
                            <div key={posKey} className="flex items-center gap-2 text-xs">
                              <Badge variant="outline" className="text-[9px] border-white/10 text-slate-500 shrink-0 w-7 justify-center">
                                {posKey.replace('P', '')}
                              </Badge>
                              <span className={`inline-flex items-center h-6 min-w-6 justify-center rounded-full text-[11px] font-mono font-bold ${BLOCK_COLOR_CLASSES[color]?.badge || 'bg-white/10 text-slate-300 border-white/10'}`}>
                                {selected}
                              </span>
                              {sortedVotes.length > 1 && (
                                <div className="flex gap-0.5 ml-1">
                                  {sortedVotes.slice(1, 4).map(([num, score]) => (
                                    <span key={num} className="text-[9px] text-slate-500 font-mono">{num}({(score as number).toFixed(1)})</span>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          )}

          {/* Individual Predictions */}
          {pipelineResult.individual_predictions && pipelineResult.individual_predictions.length > 0 && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center gap-2">
                  <GitBranch className="h-3.5 w-3.5 text-slate-400" />
                  Индивидуальные прогоны (первые 3)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 max-h-64 overflow-y-auto">
                {pipelineResult.individual_predictions.map((pred, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Badge variant="outline" className="text-[10px] border-white/10 text-slate-500 shrink-0">
                      #{i + 1}
                    </Badge>
                    <div className="flex flex-wrap gap-1">
                      {pred.block1.map((n, j) => (
                        <span key={j} className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-white/5 text-slate-400">
                          {n}
                        </span>
                      ))}
                      <span className="text-slate-600 mx-1">+</span>
                      {pred.block2.map((n, j) => (
                        <span key={j} className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-white/5 text-slate-400">
                          {n}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </motion.div>
      )}
    </motion.div>
  )
}
