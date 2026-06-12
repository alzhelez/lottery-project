'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Crown, ArrowLeft, Target, TrendingUp, TrendingDown, Minus,
  Zap, BarChart3, Activity, Shield, Crosshair, Award,
  Clock, Layers, CheckCircle2, AlertTriangle, ChevronDown, ChevronRight,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'
import type { GodModeResult, GodModeRun, WizardStep } from './types'
import { fadeIn, fadeInInstant } from './types'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { GAME_FORMATS } from './types'

interface GodModeResultsProps {
  result: GodModeResult
  gameName: string
  gameKey: string
  setStep: (step: WizardStep) => void
  onReset: () => void
}

export function GodModeResults({ result, gameName, gameKey, setStep, onReset }: GodModeResultsProps) {
  const reducedMotion = usePrefersReducedMotion()
  const anim = reducedMotion ? fadeInInstant : fadeIn
  const [expandedRun, setExpandedRun] = useState<number | null>(null)

  const runs = result.runs || []
  const successfulRuns = runs.filter(r => !r.error)
  const failedRuns = runs.filter(r => r.error)
  const summary = result.analysis_summary
  const bestCombinations = result.best_combinations || []

  const fmt = GAME_FORMATS[gameKey]

  const hitsColor = (total: number) => {
    if (total >= 3) return 'text-emerald-400'
    if (total === 2) return 'text-amber-400'
    return 'text-red-400'
  }

  const trendIcon = (trend: string) => {
    if (trend === 'improving') return <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
    if (trend === 'declining') return <TrendingDown className="h-3.5 w-3.5 text-red-400" />
    return <Minus className="h-3.5 w-3.5 text-slate-400" />
  }

  const confidenceColor = (conf: number) => {
    if (conf >= 70) return 'border-emerald-500/30 text-emerald-300 bg-emerald-500/10'
    if (conf >= 40) return 'border-amber-500/30 text-amber-300 bg-amber-500/10'
    return 'border-red-500/30 text-red-300 bg-red-500/10'
  }

  const renderNums = (nums: number[], variant: 'blue' | 'emerald' | 'amber' = 'blue') => (
    <div className="flex flex-wrap gap-1.5">
      {nums.map((n, i) => {
        const cls = variant === 'amber'
          ? 'bg-gradient-to-br from-amber-500 to-orange-400 text-white shadow-amber-500/20'
          : variant === 'emerald'
            ? 'bg-gradient-to-br from-emerald-500 to-teal-400 text-white shadow-emerald-500/20'
            : 'bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-blue-500/20'
        return (
          <span
            key={i}
            className={`inline-flex items-center h-9 min-w-9 justify-center rounded-full text-sm font-mono font-bold shadow-md ${cls}`}
          >
            {n}
          </span>
        )
      })}
    </div>
  )

  return (
    <motion.div key="god-mode-results" {...anim}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <Button variant="ghost" size="sm" onClick={() => setStep(2)} className="text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4 mr-1" /> Назад
        </Button>
        <div className="flex items-center gap-2">
          <Crown className="h-5 w-5 text-amber-400" />
          <h2 className="text-lg font-bold">Режим Бога: {gameName}</h2>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400">
            {result.total_runs} прогонов
          </Badge>
          {result.total_elapsed_seconds && (
            <Badge variant="outline" className="text-[10px] border-white/10 text-slate-400">
              <Clock className="h-3 w-3 mr-1" />
              {Math.round(result.total_elapsed_seconds / 60)}мин
            </Badge>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {/* ── Best Combinations ──────────────────────────────────────── */}
        {bestCombinations.map((combo, idx) => (
          <Card
            key={idx}
            className={idx === 0
              ? 'border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent overflow-hidden relative'
              : 'border-white/10 bg-white/5 backdrop-blur-sm'
            }
          >
            {idx === 0 && <div className="absolute top-0 right-0 w-40 h-40 bg-amber-500/5 rounded-full blur-3xl" />}
            <CardHeader className="pb-2 relative">
              <CardTitle className="text-sm flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-400" />
                {idx === 0 ? 'Наиболее вероятная комбинация' : `Альтернатива #${idx + 1}`}
                <Badge className={`text-[10px] ${confidenceColor(combo.confidence)}`}>
                  {combo.confidence.toFixed(0)}%
                </Badge>
                {idx === 0 && <Badge variant="outline" className="text-[9px] border-amber-500/30 text-amber-300 ml-auto">Лучшая</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent className="relative space-y-3">
              {/* Numbers */}
              <div className="space-y-2">
                <div>
                  <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Блок 1 {fmt ? `(${fmt.pick_b1} из ${fmt.b1_range})` : ''}</p>
                  {renderNums(combo.block1, 'blue')}
                </div>
                {combo.block2.length > 0 && (
                  <div>
                    <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Блок 2 {fmt ? `(${fmt.pick_b2} из ${fmt.b2_range})` : ''}</p>
                    {renderNums(combo.block2, 'emerald')}
                  </div>
                )}
              </div>

              {/* Reasoning */}
              <div className="rounded-lg bg-white/5 p-3">
                <p className="text-[10px] text-slate-500 mb-1 font-medium">Обоснование</p>
                <p className="text-xs text-slate-300 leading-relaxed">{combo.reasoning}</p>
              </div>

              {/* Method */}
              <p className="text-[10px] text-slate-500">
                Метод: <span className="text-slate-400">{combo.method}</span>
              </p>
            </CardContent>
          </Card>
        ))}

        {/* ── Summary Stats ──────────────────────────────────────────── */}
        {summary && (
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-violet-400" />
                Сводная статистика
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { label: 'Среднее попаданий', value: summary.avg_hits.toFixed(2), color: 'text-white' },
                  { label: 'Лучший прогон', value: `#${summary.best_run}`, color: 'text-amber-400' },
                  { label: 'Стабильность', value: `${(summary.consistency_score * 100).toFixed(0)}%`, color: summary.consistency_score >= 0.5 ? 'text-emerald-400' : 'text-amber-400' },
                  { label: 'Надёжность', value: `${(summary.avg_reliability * 100).toFixed(0)}%`, color: summary.avg_reliability >= 0.5 ? 'text-emerald-400' : 'text-red-400' },
                ].map((stat) => (
                  <div key={stat.label} className="rounded-lg bg-white/5 p-2.5 text-center">
                    <div className="text-[10px] text-slate-400 mb-0.5">{stat.label}</div>
                    <div className={`text-sm font-mono font-bold ${stat.color}`}>{stat.value}</div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Успешных прогонов</span>
                  <span className="font-mono text-emerald-400">{summary.total_successful}/{result.total_runs}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Согласие Б1</span>
                  <span className="font-mono text-white">{(summary.avg_consensus_b1 * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Согласие Б2</span>
                  <span className="font-mono text-white">{(summary.avg_consensus_b2 * 100).toFixed(1)}%</span>
                </div>
              </div>

              {/* Trend summary */}
              {summary.trend_summary && Object.keys(summary.trend_summary).length > 0 && (
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-slate-400">Тренды:</span>
                  <div className="flex gap-3">
                    {Object.entries(summary.trend_summary).map(([trend, count]) => (
                      <span key={trend} className="flex items-center gap-1">
                        {trendIcon(trend)}
                        <span className="text-slate-300">
                          {trend === 'improving' ? 'улучшается' : trend === 'declining' ? 'ухудшается' : trend === 'stable' ? 'стабильно' : trend}
                        </span>
                        <Badge variant="outline" className="text-[9px] border-white/10 text-slate-500">{count}</Badge>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* ── Best Combination Votes ─────────────────────────────────── */}
        {summary?.best_combination_votes && (
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs flex items-center gap-2">
                <Crosshair className="h-3.5 w-3.5 text-blue-400" />
                Голосование по лучшим числам
              </CardTitle>
              <p className="text-[10px] text-slate-500">Процент прогонов, в которых число появилось в прогнозе</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {(['block1', 'block2'] as const).map(block => {
                  const votes = summary.best_combination_votes[block]
                  if (!votes || Object.keys(votes).length === 0) return null
                  const label = block === 'block1' ? 'Блок 1' : 'Блок 2'
                  const maxVotes = Math.max(...Object.values(votes))
                  return (
                    <div key={block}>
                      <p className="text-[10px] text-slate-400 mb-1 font-medium">{label}</p>
                      <div className="space-y-1">
                        {Object.entries(votes)
                          .sort((a, b) => b[1] - a[1])
                          .map(([num, pct]) => (
                            <div key={num} className="flex items-center gap-2">
                              <span className="text-[10px] font-mono text-slate-300 w-6 text-right">{num}</span>
                              <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-500/60'}`}
                                  style={{ width: `${(pct / maxVotes) * 100}%` }}
                                />
                              </div>
                              <span className="text-[10px] font-mono text-slate-400 w-10 text-right">{pct}%</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── Top Numbers ─────────────────────────────────────────────── */}
        {summary?.top_numbers && (summary.top_numbers.block1.length > 0 || summary.top_numbers.block2.length > 0) && (
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs flex items-center gap-2">
                <BarChart3 className="h-3.5 w-3.5 text-cyan-400" />
                Самые популярные числа (по всем прогонам)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <p className="text-[10px] text-blue-400/60 mb-1">Блок 1</p>
                <div className="flex flex-wrap gap-1">
                  {summary.top_numbers.block1.map((n, i) => (
                    <span key={i} className="inline-flex items-center h-6 min-w-6 justify-center rounded text-[10px] font-mono bg-blue-500/15 text-blue-300">{n}</span>
                  ))}
                </div>
              </div>
              {summary.top_numbers.block2.length > 0 && (
                <div>
                  <p className="text-[10px] text-emerald-400/60 mb-1">Блок 2</p>
                  <div className="flex flex-wrap gap-1">
                    {summary.top_numbers.block2.map((n, i) => (
                      <span key={i} className="inline-flex items-center h-6 min-w-6 justify-center rounded text-[10px] font-mono bg-emerald-500/15 text-emerald-300">{n}</span>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* ── Per-Run Table ───────────────────────────────────────────── */}
        <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs flex items-center gap-2">
              <Layers className="h-3.5 w-3.5 text-slate-400" />
              Результаты по прогонам
              <Badge variant="outline" className="text-[9px] border-white/10 text-slate-500 ml-auto">
                {successfulRuns.length} успешных · {failedRuns.length} ошибок
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-[#0d1225]">
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="text-left py-2 pr-2 font-medium">#</th>
                    <th className="text-left py-2 pr-2 font-medium">Параметры</th>
                    <th className="text-left py-2 pr-2 font-medium">Прогноз</th>
                    <th className="text-center py-2 px-2 font-medium">Б1</th>
                    <th className="text-center py-2 px-2 font-medium">Б2</th>
                    <th className="text-center py-2 px-2 font-medium">Попад.</th>
                    <th className="text-center py-2 px-2 font-medium">Время</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => {
                    const isExpanded = expandedRun === run.run_id
                    const pred = run.prediction
                    const sa = run.step_analysis
                    const hasError = !!run.error
                    return (
                      <motion.tr
                        key={run.run_id}
                        onClick={() => setExpandedRun(isExpanded ? null : run.run_id)}
                        className={`border-b border-white/5 cursor-pointer hover:bg-white/5 transition-colors ${hasError ? 'opacity-50' : ''}`}
                      >
                        <td className="py-2 pr-2">
                          <div className="flex items-center gap-1">
                            {isExpanded ? <ChevronDown className="h-3 w-3 text-slate-500" /> : <ChevronRight className="h-3 w-3 text-slate-500" />}
                            <span className="font-mono text-slate-300">{run.run_id}</span>
                          </div>
                        </td>
                        <td className="py-2 pr-2">
                          <span className="text-[10px] text-slate-500">
                            {run.params.rangeFrom}-{run.params.rangeTo} · {run.params.steps_n} шагов
                          </span>
                        </td>
                        <td className="py-2 pr-2">
                          {pred ? (
                            <div className="flex gap-0.5">
                              {pred.block1.slice(0, 4).map((n, i) => (
                                <span key={`b1-${i}`} className="inline-flex h-4 min-w-4 justify-center rounded text-[8px] font-mono bg-blue-500/15 text-blue-300">{n}</span>
                              ))}
                              {pred.block2.length > 0 && (
                                <>
                                  <span className="text-slate-600 mx-0.5">+</span>
                                  {pred.block2.map((n, i) => (
                                    <span key={`b2-${i}`} className="inline-flex h-4 min-w-4 justify-center rounded text-[8px] font-mono bg-emerald-500/15 text-emerald-300">{n}</span>
                                  ))}
                                </>
                              )}
                            </div>
                          ) : (
                            <span className="text-red-400 text-[10px]">ошибка</span>
                          )}
                        </td>
                        <td className="py-2 px-2 text-center">
                          {pred ? (
                            <span className={`text-[10px] font-mono ${hitsColor(Number((sa?.avg_hits ?? 0) as number))}`}>
                              {(sa?.avg_hits as number)?.toFixed(1) ?? '—'}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="py-2 px-2 text-center text-[10px] font-mono text-slate-400">
                          {pred ? (
                            <span className={hitsColor(Number((sa?.max_hits ?? 0) as number))}>
                              {sa?.max_hits as number ?? '—'}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="py-2 px-2 text-center text-[10px] text-slate-500">
                          {run.elapsed_seconds}с
                        </td>
                      </motion.tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Expanded run details */}
            <AnimatePresence>
              {expandedRun !== null && (() => {
                const run = runs.find(r => r.run_id === expandedRun)
                if (!run) return null
                const sa = run.step_analysis
                const pred = run.prediction
                const pl = run.pipeline
                return (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: reducedMotion ? 0 : 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="border-t border-white/10 p-4 bg-white/[0.02] rounded-b-lg space-y-3">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <div className="rounded-md bg-white/5 p-2">
                          <div className="text-[9px] text-slate-500">Диапазон</div>
                          <div className="text-xs font-mono text-white">{run.params.rangeFrom}–{run.params.rangeTo}</div>
                        </div>
                        <div className="rounded-md bg-white/5 p-2">
                          <div className="text-[9px] text-slate-500">Шаги анализа</div>
                          <div className="text-xs font-mono text-white">{run.params.steps_n}</div>
                        </div>
                        {sa && (
                          <>
                            <div className="rounded-md bg-white/5 p-2">
                              <div className="text-[9px] text-slate-500">Надёжность</div>
                              <div className={`text-xs font-mono ${Number(sa.reliability_score) >= 0.5 ? 'text-emerald-400' : 'text-amber-400'}`}>
                                {((sa.reliability_score as number) * 100).toFixed(0)}%
                              </div>
                            </div>
                            <div className="rounded-md bg-white/5 p-2">
                              <div className="text-[9px] text-slate-500">Тренд</div>
                              <div className="text-xs text-slate-300 flex items-center gap-1">
                                {trendIcon(sa.trend as string)}
                                {sa.trend === 'improving' ? 'Улучшается' : sa.trend === 'declining' ? 'Ухудшается' : sa.trend === 'stable' ? 'Стабильно' : String(sa.trend)}
                              </div>
                            </div>
                          </>
                        )}
                      </div>

                      {/* Step analysis details */}
                      {sa && (sa as Record<string, unknown>).analysis_text && (
                        <div className="rounded-md bg-white/5 p-2">
                          <p className="text-[9px] text-slate-500 mb-0.5">Анализ</p>
                          <p className="text-[10px] text-slate-300 leading-relaxed">{String((sa as Record<string, unknown>).analysis_text)}</p>
                        </div>
                      )}

                      {/* Consensus numbers */}
                      {sa && (sa.consensus_b1 as number[] | undefined) && (
                        <div className="flex gap-4">
                          <div>
                            <p className="text-[9px] text-blue-400/60 mb-0.5">Консенсус Б1</p>
                            <div className="flex flex-wrap gap-0.5">
                              {(sa.consensus_b1 as number[]).map((n, i) => (
                                <span key={i} className="inline-flex h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-blue-500/15 text-blue-300">{n}</span>
                              ))}
                            </div>
                          </div>
                          {sa.consensus_b2 && (sa.consensus_b2 as number[]).length > 0 && (
                            <div>
                              <p className="text-[9px] text-emerald-400/60 mb-0.5">Консенсус Б2</p>
                              <div className="flex flex-wrap gap-0.5">
                                {(sa.consensus_b2 as number[]).map((n, i) => (
                                  <span key={i} className="inline-flex h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-emerald-500/15 text-emerald-300">{n}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Pipeline details */}
                      {pl && (
                        <div className="flex items-center gap-4 text-[10px]">
                          <span className="text-slate-500">Pipeline уверенность:</span>
                          <span className="font-mono text-white">{((pl.confidence_overall ?? 0) * 100).toFixed(0)}%</span>
                        </div>
                      )}

                      {run.error && (
                        <p className="text-[10px] text-red-400">Ошибка: {run.error}</p>
                      )}
                    </div>
                  </motion.div>
                )
              })()}
            </AnimatePresence>
          </CardContent>
        </Card>

        {/* ── Parameters Used ────────────────────────────────────────── */}
        {summary?.parameters_used && summary.parameters_used.length > 0 && (
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 text-slate-400" />
                Использованные параметры
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1.5">
                {summary.parameters_used.map((p, i) => (
                  <Badge key={i} variant="outline" className="text-[9px] border-white/10 text-slate-400">
                    {p}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── Reset button ───────────────────────────────────────────── */}
        <Button
          onClick={onReset}
          variant="outline"
          className="w-full h-10 border-white/10 text-slate-400 hover:bg-white/5 text-xs"
        >
          <CheckCircle2 className="h-3.5 w-3.5 mr-2" />
          Вернуться к обычному режиму
        </Button>
      </div>
    </motion.div>
  )
}
