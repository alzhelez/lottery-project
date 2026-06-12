'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  FlaskConical, ChevronDown, ChevronRight,
  TrendingUp, TrendingDown, Minus, Target,
  BarChart3, Zap, Loader2, AlertTriangle, RotateCcw,
  Shield, Crosshair, Award,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { safeJsonFetch } from '@/lib/fetch'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { fadeIn, fadeInInstant } from './types'

// ── Types ──────────────────────────────────────────────────────────────────

interface StepAnalysisCardProps {
  selectedGame: { key: string; name: string }
  dataFile: string
  rangeFrom: number | null
  rangeTo: number | null
}

interface StepResult {
  step: number
  draw_no: number
  trained_on: number
  predicted: { block1: number[]; block2: number[] }
  actual: { block1: number[]; block2: number[] }
  hits: { block1: number; block2: number; total: number }
  confidence: { block1: number; block2: number }
  models_used: number
  top_numbers: { block1: number[]; block2: number[] }
  comparison: { overlap_with_prev: { block1: number; block2: number }; new_numbers: { block1: number[]; block2: number[] } } | null
  hit_positions: number[]
}

interface StepAnalysisResult {
  status: 'ok'
  n_steps: number
  draws_analyzed: number
  game_format: string
  draw_range: { first: number; last: number }
  elapsed_seconds: number
  steps: StepResult[]
  final_prediction: {
    block1: number[]
    block2: number[]
    confidence: { block1: number; block2: number }
    expected_hits: { avg: number; median: number; min: number; max: number }
    most_reliable_numbers: { block1: number[]; block2: number[] }
    reliability_score: number
    strong_numbers: { block1: number[]; block2: number[] }
    consensus_numbers: { block1: number[]; block2: number[] }
    strongest_numbers: { block1: number[]; block2: number[] }
    confidence_level: 'high' | 'medium' | 'low'
    confidence_text: string
    analysis: string
  }
  summary: {
    avg_hits: number
    median_hits: number
    max_hits: number
    min_hits: number
    trend: 'improving' | 'declining' | 'stable' | 'insufficient_data'
    hit_distribution: Record<string, number>
    consistency: number
    best_step: number
    total_numbers: number
  }
}

// ── Component ──────────────────────────────────────────────────────────────

export function StepAnalysisCard({ selectedGame, dataFile, rangeFrom, rangeTo }: StepAnalysisCardProps) {
  const reducedMotion = usePrefersReducedMotion()
  const anim = reducedMotion ? fadeInInstant : fadeIn

  const [nSteps, setNSteps] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<StepAnalysisResult | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [expandedRow, setExpandedRow] = useState<number | null>(null)

  const timerRef = useRef<ReturnType<typeof setInterval>>()
  const pollRef = useRef<ReturnType<typeof setInterval>>()
  const startTsRef = useRef<number>(0)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const poll = useCallback(async (forceRefresh = false) => {
    const { data, ok } = await safeJsonFetch<{
      status: string; _refreshing?: boolean
    } & Partial<StepAnalysisResult>>('/api/lottery/step-analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game: selectedGame.key,
        data_file: dataFile,
        steps: nSteps,
        from_draw: rangeFrom,
        to_draw: rangeTo,
        _force: forceRefresh,
      }),
    }, 120_000)

    if (ok && data.status === 'ok' && data.steps && data.steps.length > 0) {
      setResult(data as StepAnalysisResult)
      setLoading(false)
      if (timerRef.current) clearInterval(timerRef.current)
      if (pollRef.current) clearInterval(pollRef.current)
      setElapsed(Math.round((Date.now() - startTsRef.current) / 1000))
    } else if (ok && data.status === 'error') {
      const err = (data as Record<string, unknown>)?.error as string | undefined
      const hint = (data as Record<string, unknown>)?.hint as string | undefined
      setError(hint ? `${err || 'Ошибка'}\n${hint}` : (err || 'Ошибка анализа'))
      setLoading(false)
      if (timerRef.current) clearInterval(timerRef.current)
      if (pollRef.current) clearInterval(pollRef.current)
    } else if (ok && data._refreshing && data.status === 'pending') {
      // Still pending, keep polling
    } else if (!ok) {
      const err = (data as Record<string, unknown>)?.error as string | undefined
      setError(err || 'Ошибка запроса')
      setLoading(false)
      if (timerRef.current) clearInterval(timerRef.current)
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [selectedGame.key, dataFile, nSteps, rangeFrom, rangeTo])

  const handleStart = useCallback(() => {
    setError(null)
    setResult(null)
    setExpandedRow(null)
    setLoading(true)
    setElapsed(0)
    startTsRef.current = Date.now()

    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setElapsed(Math.round((Date.now() - startTsRef.current) / 1000))
    }, 1000)

    // Initial request with force refresh to clear stale cache
    poll(true).then(() => {
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = setInterval(poll, 3000)
    })
  }, [poll])

  const handleReset = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (pollRef.current) clearInterval(pollRef.current)
    setLoading(false)
    setError(null)
    setResult(null)
    setElapsed(0)
    setExpandedRow(null)
  }, [])

  // ── Helpers ───────────────────────────────────────────────────────────

  const hitsColor = (total: number) => {
    if (total >= 3) return 'text-emerald-400'
    if (total === 2) return 'text-amber-400'
    return 'text-red-400'
  }

  const hitsBg = (total: number) => {
    if (total >= 3) return 'bg-emerald-500/15 border-emerald-500/20'
    if (total === 2) return 'bg-amber-500/15 border-amber-500/20'
    return 'bg-red-500/15 border-red-500/20'
  }

  const trendIcon = (trend: string) => {
    if (trend === 'improving') return <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
    if (trend === 'declining') return <TrendingDown className="h-3.5 w-3.5 text-red-400" />
    return <Minus className="h-3.5 w-3.5 text-slate-400" />
  }

  const trendLabel = (trend: string) => {
    if (trend === 'improving') return 'улучшается'
    if (trend === 'declining') return 'ухудшается'
    if (trend === 'stable') return 'стабильно'
    return 'мало данных'
  }

  const confidenceColor = (level: string) => {
    if (level === 'high') return 'border-emerald-500/30 text-emerald-300 bg-emerald-500/10'
    if (level === 'medium') return 'border-amber-500/30 text-amber-300 bg-amber-500/10'
    return 'border-red-500/30 text-red-300 bg-red-500/10'
  }

  const reliabilityColor = (score: number) => {
    if (score >= 0.7) return 'text-emerald-400'
    if (score >= 0.4) return 'text-amber-400'
    return 'text-red-400'
  }

  const renderNums = (nums: number[], isHit?: (n: number) => boolean) => (
    <div className="flex flex-wrap gap-0.5">
      {nums.map((n, i) => (
        <span
          key={i}
          className={`inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono ${
            isHit?.(n)
              ? 'bg-violet-500/20 text-violet-300 ring-1 ring-violet-500/40'
              : 'bg-white/10 text-slate-400'
          }`}
        >
          {n}
        </span>
      ))}
    </div>
  )

  // ── Controls (initial state) ──────────────────────────────────────────

  if (!loading && !result && !error) {
    return (
      <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-violet-400" />
            Поэтапный анализ
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-slate-400">
            Последовательный прогноз на N последних тиражей с проверкой по реальным результатам
          </p>
          <div className="flex items-center gap-3">
            <label className="text-xs text-slate-400 shrink-0">Количество шагов:</label>
            <input
              type="number"
              min={1}
              max={10}
              value={nSteps}
              onChange={(e) => setNSteps(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
              className="h-8 w-20 rounded-md border border-white/10 bg-white/5 px-2 text-xs text-white text-center focus:outline-none focus:ring-1 focus:ring-violet-500/50"
            />
            <span className="text-[10px] text-slate-500">от 1 до 10</span>
          </div>
          <Button
            onClick={handleStart}
            className="h-9 px-4 bg-gradient-to-r from-violet-600 to-purple-500 hover:from-violet-500 hover:to-purple-400 text-white text-xs font-medium"
          >
            <FlaskConical className="h-3.5 w-3.5 mr-1.5" />
            Запустить анализ
          </Button>
        </CardContent>
      </Card>
    )
  }

  // ── Loading state ─────────────────────────────────────────────────────

  if (loading) {
    return (
      <Card className="border-violet-500/30 bg-violet-500/5">
        <CardContent className="py-8 flex flex-col items-center gap-4">
          <Loader2 className="h-10 w-10 text-violet-400 animate-spin" />
          <div className="text-center">
            <p className="text-sm font-medium text-violet-300">Поэтапный анализ...</p>
            <p className="text-xs text-slate-400 mt-1">
              Обучение и проверка на {nSteps} шагах
            </p>
          </div>
          <div className="w-full max-w-xs space-y-2">
            <Progress value={Math.min(92, Math.max(5, elapsed * 1.2))} className="h-2 bg-white/10" />
            <p className="text-[10px] text-slate-500 text-center">
              {elapsed > 0 ? `Прошло ${elapsed}с — модели анализируют данные...` : 'Запуск анализа...'}
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  // ── Error state ───────────────────────────────────────────────────────

  if (error) {
    return (
      <Card className="border-red-500/30 bg-red-500/5">
        <CardContent className="py-6 flex flex-col items-center gap-3">
          <AlertTriangle className="h-8 w-8 text-red-400" />
          <p className="text-sm text-red-400 text-center whitespace-pre-line">{error}</p>
          <Button variant="outline" size="sm" onClick={handleStart} className="border-red-500/30 text-red-400">
            <RotateCcw className="h-3.5 w-3.5 mr-1" /> Повторить
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (!result) return null

  // ── Results ───────────────────────────────────────────────────────────

  return (
    <motion.div className="space-y-4" {...anim}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-violet-400" />
          <span className="text-sm font-semibold text-white">Поэтапный анализ</span>
          <Badge variant="outline" className="text-[10px] border-violet-500/30 text-violet-400">
            {result.n_steps} шагов · {result.elapsed_seconds}с
          </Badge>
          <Badge variant="outline" className="text-[10px] border-white/10 text-slate-400">
            {result.game_format}
          </Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={handleReset} className="text-slate-400 hover:text-white h-7 px-2">
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Per-step table */}
      <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs flex items-center gap-2">
            <BarChart3 className="h-3.5 w-3.5 text-blue-400" />
            Результаты по шагам
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="text-left py-2 pr-2 font-medium">Шаг</th>
                  <th className="text-left py-2 pr-2 font-medium">Тираж №</th>
                  <th className="text-left py-2 pr-2 font-medium">Предсказание</th>
                  <th className="text-left py-2 pr-2 font-medium">Реальный</th>
                  <th className="text-center py-2 px-2 font-medium">Попад.</th>
                  <th className="text-center py-2 pl-2 font-medium">Conf.</th>
                </tr>
              </thead>
              <tbody>
                {result.steps.map((sr) => {
                  const isExpanded = expandedRow === sr.step
                  return (
                    <motion.tr
                      key={sr.step}
                      onClick={() => setExpandedRow(isExpanded ? null : sr.step)}
                      className="border-b border-white/5 cursor-pointer hover:bg-white/5 transition-colors"
                    >
                      <td className="py-2 pr-2">
                        <div className="flex items-center gap-1">
                          {isExpanded ? (
                            <ChevronDown className="h-3 w-3 text-slate-500" />
                          ) : (
                            <ChevronRight className="h-3 w-3 text-slate-500" />
                          )}
                          <span className="font-mono text-slate-300">{sr.step}</span>
                        </div>
                      </td>
                      <td className="py-2 pr-2 font-mono text-slate-300">#{sr.draw_no}</td>
                      <td className="py-2 pr-2">
                        <div className="flex flex-col gap-0.5">
                          <div className="flex flex-wrap gap-0.5">
                            {sr.predicted.block1.map((n, i) => (
                              <span key={i} className="inline-flex h-4 min-w-4 justify-center rounded text-[8px] font-mono bg-blue-500/15 text-blue-300">{n}</span>
                            ))}
                          </div>
                          {sr.predicted.block2.length > 0 && (
                            <div className="flex flex-wrap gap-0.5">
                              {sr.predicted.block2.map((n, i) => (
                                <span key={i} className="inline-flex h-4 min-w-4 justify-center rounded text-[8px] font-mono bg-emerald-500/15 text-emerald-300">{n}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="py-2 pr-2">
                        <div className="flex flex-col gap-0.5">
                          <div className="flex flex-wrap gap-0.5">
                            {sr.actual.block1.map((n, i) => (
                              <span key={i} className="inline-flex h-4 min-w-4 justify-center rounded text-[8px] font-mono bg-white/10 text-slate-400">{n}</span>
                            ))}
                          </div>
                          {sr.actual.block2.length > 0 && (
                            <div className="flex flex-wrap gap-0.5">
                              {sr.actual.block2.map((n, i) => (
                                <span key={i} className="inline-flex h-4 min-w-4 justify-center rounded text-[8px] font-mono bg-white/10 text-slate-400">{n}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="py-2 px-2 text-center">
                        <span className={`inline-flex items-center h-5 px-1.5 rounded border text-[10px] font-mono font-bold ${hitsColor(sr.hits.total)} ${hitsBg(sr.hits.total)}`}>
                          {sr.hits.total}
                          <span className="text-[8px] opacity-60 ml-0.5">({sr.hits.block1}+{sr.hits.block2})</span>
                        </span>
                      </td>
                      <td className="py-2 pl-2 text-center font-mono text-slate-400 text-[10px]">
                        {((sr.confidence.block1 + sr.confidence.block2) / 2 * 100).toFixed(0)}%
                      </td>
                    </motion.tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Expanded row details */}
          <AnimatePresence>
            {expandedRow !== null && (() => {
              const sr = result.steps.find((s) => s.step === expandedRow)
              if (!sr) return null
              return (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: reducedMotion ? 0 : 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="border-t border-white/10 p-4 space-y-3 bg-white/[0.02] rounded-b-lg">
                    <div>
                      <p className="text-[10px] text-slate-500 mb-1.5 font-medium uppercase tracking-wider">Топ чисел по моделям</p>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] text-blue-400/60 w-6">Б1:</span>
                          {renderNums(sr.top_numbers.block1)}
                        </div>
                        {sr.top_numbers.block2.length > 0 && (
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] text-emerald-400/60 w-6">Б2:</span>
                            {renderNums(sr.top_numbers.block2)}
                          </div>
                        )}
                      </div>
                    </div>
                    {sr.comparison && (
                      <div>
                        <p className="text-[10px] text-slate-500 mb-1.5 font-medium uppercase tracking-wider">Сравнение с предыдущим шагом</p>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="rounded-md bg-white/5 p-2 text-center">
                            <div className="text-[9px] text-slate-500 mb-0.5">Пересечение Б1</div>
                            <div className="text-sm font-mono font-bold text-blue-300">{sr.comparison.overlap_with_prev.block1}</div>
                          </div>
                          <div className="rounded-md bg-white/5 p-2 text-center">
                            <div className="text-[9px] text-slate-500 mb-0.5">Пересечение Б2</div>
                            <div className="text-sm font-mono font-bold text-emerald-300">{sr.comparison.overlap_with_prev.block2}</div>
                          </div>
                        </div>
                        {sr.comparison.new_numbers.block1.length > 0 && (
                          <div className="mt-2 space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[9px] text-blue-400/60 w-12">Новые Б1:</span>
                              {renderNums(sr.comparison.new_numbers.block1)}
                            </div>
                            {sr.comparison.new_numbers.block2.length > 0 && (
                              <div className="flex items-center gap-2">
                                <span className="text-[9px] text-emerald-400/60 w-12">Новые Б2:</span>
                                {renderNums(sr.comparison.new_numbers.block2)}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    <div className="flex items-center gap-4 text-[10px] text-slate-500 pt-1 border-t border-white/5">
                      <span>Обучено на {sr.trained_on} тиражах</span>
                      <span>{sr.models_used} моделей</span>
                      {sr.hit_positions.length > 0 && (
                        <span>Попадания: {sr.hit_positions.join(', ')}</span>
                      )}
                    </div>
                  </div>
                </motion.div>
              )
            })()}
          </AnimatePresence>
        </CardContent>
      </Card>

      {/* Summary card */}
      <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs flex items-center gap-2">
            <Target className="h-3.5 w-3.5 text-amber-400" />
            Сводка по попаданиям
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {[
              { label: 'Среднее', value: result.summary.avg_hits.toFixed(2), color: 'text-white' },
              { label: 'Медиана', value: String(result.summary.median_hits), color: 'text-white' },
              { label: 'Максимум', value: String(result.summary.max_hits), color: 'text-emerald-400' },
              { label: 'Минимум', value: String(result.summary.min_hits), color: 'text-red-400' },
              { label: 'Стабильность', value: (result.summary.consistency * 100).toFixed(0) + '%', color: result.summary.consistency >= 0.7 ? 'text-emerald-400' : result.summary.consistency >= 0.4 ? 'text-amber-400' : 'text-red-400' },
            ].map((stat) => (
              <div key={stat.label} className="rounded-lg bg-white/5 p-2.5 text-center">
                <div className="text-[10px] text-slate-400 mb-0.5">{stat.label}</div>
                <div className={`text-sm font-mono font-bold ${stat.color}`}>{stat.value}</div>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              {trendIcon(result.summary.trend)}
              <span className="capitalize">{trendLabel(result.summary.trend)}</span>
            </div>
            <div className="text-xs text-slate-500">
              Лучший шаг: <span className="font-mono text-amber-300 font-bold">#{result.summary.best_step}</span>
            </div>
          </div>

          {Object.keys(result.summary.hit_distribution).length > 0 && (() => {
            const dist = result.summary.hit_distribution
            const maxCount = Math.max(...Object.values(dist), 1)
            const sortedKeys = Object.keys(dist).sort((a, b) => Number(a) - Number(b))
            return (
              <div>
                <p className="text-[10px] text-slate-500 mb-1.5 font-medium uppercase tracking-wider">Распределение попаданий</p>
                <div className="flex items-end gap-1 h-12">
                  {sortedKeys.map((key) => {
                    const count = dist[key]
                    const pct = (count / maxCount) * 100
                    const hitVal = Number(key)
                    const barColor = hitVal >= 3 ? 'bg-emerald-500' : hitVal === 2 ? 'bg-amber-500' : 'bg-red-500/60'
                    return (
                      <div key={key} className="flex-1 flex flex-col items-center gap-0.5">
                        <span className="text-[8px] text-slate-500 font-mono">{count}</span>
                        <div className="w-full flex items-end" style={{ height: '2rem' }}>
                          <div className={`w-full rounded-t ${barColor} transition-all`} style={{ height: `${Math.max(pct, 8)}%` }} />
                        </div>
                        <span className="text-[8px] text-slate-500">{hitVal}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })()}
        </CardContent>
      </Card>

      {/* Final Prediction card */}
      <Card className="border-violet-500/20 bg-gradient-to-br from-violet-500/10 via-purple-500/5 to-transparent overflow-hidden relative">
        <div className="absolute top-0 right-0 w-40 h-40 bg-violet-500/5 rounded-full blur-3xl" />
        <CardHeader className="pb-2 relative">
          <CardTitle className="text-sm flex items-center gap-2">
            <Zap className="h-4 w-4 text-violet-400" />
            Финальный прогноз
          </CardTitle>
        </CardHeader>
        <CardContent className="relative space-y-4">
          {/* Expected hits + Confidence + Reliability */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-white/5 p-3 text-center">
              <div className="text-[10px] text-slate-400 mb-1">Ожидаемые попадания</div>
              <div className="text-lg font-bold text-white">
                {result.final_prediction.expected_hits.avg}–{result.final_prediction.expected_hits.max}
              </div>
              <div className="text-[10px] text-slate-500">
                медиана: {result.final_prediction.expected_hits.median}
              </div>
            </div>
            <div className="rounded-lg bg-white/5 p-3 text-center">
              <div className="text-[10px] text-slate-400 mb-1">Уверенность</div>
              <Badge className={`text-[10px] mt-1 ${confidenceColor(result.final_prediction.confidence_level)}`}>
                {result.final_prediction.confidence_level === 'high' ? 'Высокая' : result.final_prediction.confidence_level === 'medium' ? 'Средняя' : 'Низкая'}
              </Badge>
              <p className="text-[10px] text-slate-500 mt-1">{result.final_prediction.confidence_text}</p>
            </div>
            <div className="rounded-lg bg-white/5 p-3 text-center">
              <div className="text-[10px] text-slate-400 mb-1">Надёжность прогноза</div>
              <div className={`text-lg font-bold ${reliabilityColor(result.final_prediction.reliability_score)}`}>
                {(result.final_prediction.reliability_score * 100).toFixed(0)}%
              </div>
              <Progress value={result.final_prediction.reliability_score * 100} className="h-1 bg-white/10 mt-1" />
            </div>
          </div>

          {/* Most reliable numbers */}
          {(result.final_prediction.most_reliable_numbers.block1.length > 0 || result.final_prediction.most_reliable_numbers.block2.length > 0) && (
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 space-y-2">
              <div className="flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 text-amber-400" />
                <p className="text-[10px] text-amber-300 font-medium uppercase tracking-wider">Наиболее надёжные числа</p>
              </div>
              <div className="space-y-1">
                {result.final_prediction.most_reliable_numbers.block1.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-blue-400/60 w-6">Б1:</span>
                    <div className="flex flex-wrap gap-0.5">
                      {result.final_prediction.most_reliable_numbers.block1.map((n, i) => (
                        <span
                          key={`rel-b1-${i}`}
                          className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30"
                        >
                          {n}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {result.final_prediction.most_reliable_numbers.block2.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-emerald-400/60 w-6">Б2:</span>
                    <div className="flex flex-wrap gap-0.5">
                      {result.final_prediction.most_reliable_numbers.block2.map((n, i) => (
                        <span
                          key={`rel-b2-${i}`}
                          className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30"
                        >
                          {n}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <p className="text-[9px] text-slate-500">
                Числа, которые стабильно появлялись в прогнозах на всех шагах и присутствуют в финальном предсказании
              </p>
            </div>
          )}

          {/* Consensus numbers */}
          {(result.final_prediction.consensus_numbers.block1.length > 0 || result.final_prediction.consensus_numbers.block2.length > 0) && (
            <div>
              <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider flex items-center gap-1.5">
                <Crosshair className="h-3 w-3" />
                Консенсус чисел (во всех шагах)
              </p>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-[9px] text-blue-400/60 w-6">Б1:</span>
                  {renderNums(result.final_prediction.consensus_numbers.block1)}
                </div>
                {result.final_prediction.consensus_numbers.block2.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-emerald-400/60 w-6">Б2:</span>
                    {renderNums(result.final_prediction.consensus_numbers.block2)}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Strongest numbers */}
          <div>
            <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider flex items-center gap-1.5">
              <Award className="h-3 w-3" />
              Сильнейшие числа по весам
            </p>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[9px] text-blue-400/60 w-6">Б1:</span>
                {renderNums(result.final_prediction.strongest_numbers.block1)}
              </div>
              {result.final_prediction.strongest_numbers.block2.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-[9px] text-emerald-400/60 w-6">Б2:</span>
                  {renderNums(result.final_prediction.strongest_numbers.block2)}
                </div>
              )}
            </div>
          </div>

          {/* Final prediction numbers */}
          <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-[10px] text-violet-300 font-medium uppercase tracking-wider">Прогноз на следующий тираж</p>
              <div className="flex gap-1.5">
                <Badge variant="outline" className="text-[9px] border-blue-500/30 text-blue-300">
                  Б1: {result.final_prediction.confidence.block1 != null ? (result.final_prediction.confidence.block1 * 100).toFixed(0) : '—'}%
                </Badge>
                <Badge variant="outline" className="text-[9px] border-emerald-500/30 text-emerald-300">
                  Б2: {result.final_prediction.confidence.block2 != null ? (result.final_prediction.confidence.block2 * 100).toFixed(0) : '—'}%
                </Badge>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {result.final_prediction.block1.map((n, i) => {
                const isReliable = result.final_prediction.most_reliable_numbers.block1.includes(n)
                return (
                  <span
                    key={`fp-b1-${i}`}
                    className={`inline-flex items-center h-8 min-w-8 justify-center rounded-full text-xs font-mono font-bold shadow-md ${
                      isReliable
                        ? 'bg-gradient-to-br from-amber-500 to-orange-400 text-white shadow-amber-500/20 ring-1 ring-amber-400/40'
                        : 'bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-blue-500/20'
                    }`}
                  >
                    {n}
                  </span>
                )
              })}
              <span className="inline-flex items-center text-slate-600 mx-0.5">+</span>
              {result.final_prediction.block2.map((n, i) => {
                const isReliable = result.final_prediction.most_reliable_numbers.block2.includes(n)
                return (
                  <span
                    key={`fp-b2-${i}`}
                    className={`inline-flex items-center h-8 min-w-8 justify-center rounded-full text-xs font-mono font-bold shadow-md ${
                      isReliable
                        ? 'bg-gradient-to-br from-amber-500 to-orange-400 text-white shadow-amber-500/20 ring-1 ring-amber-400/40'
                        : 'bg-gradient-to-br from-emerald-500 to-teal-400 text-white shadow-emerald-500/20'
                    }`}
                  >
                    {n}
                  </span>
                )
              })}
            </div>
            {result.final_prediction.strong_numbers.block1.length > 0 && (
              <div className="flex items-center gap-3 pt-1 border-t border-white/5 text-[10px]">
                <span className="text-slate-500">Совпадение с сильнейшими:</span>
                <span className="font-mono text-blue-300">{result.final_prediction.strong_numbers.block1.length} Б1</span>
                {result.final_prediction.strong_numbers.block2.length > 0 && (
                  <span className="font-mono text-emerald-300">{result.final_prediction.strong_numbers.block2.length} Б2</span>
                )}
              </div>
            )}
          </div>

          {/* Analysis text */}
          {result.final_prediction.analysis && (
            <div className="rounded-lg bg-white/5 p-3">
              <p className="text-[10px] text-slate-400 mb-1 font-medium">Анализ</p>
              <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">{result.final_prediction.analysis}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
