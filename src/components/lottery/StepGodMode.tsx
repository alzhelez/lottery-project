'use client'

import { useState, useMemo, useEffect, useCallback } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Shield, Zap, Loader2, AlertTriangle, ArrowLeft,
  Target, Trophy, TrendingDown, BarChart3, Play, Square,
  ChevronDown, ChevronUp, Hash, Gauge, Layers, Medal,
  Database, Crosshair,
} from 'lucide-react'
import { motion } from 'framer-motion'
import type { GameAnalysis, GodModeResult, WizardStep } from './types'
import { fadeIn, fadeInInstant, GAME_FORMATS } from './types'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

// ── Props ──────────────────────────────────────────────────────────────────────

interface StepGodModeProps {
  selectedGame: GameAnalysis
  godModeLoading: boolean
  godModeResult: GodModeResult | null
  godModeError: string | null
  godModeProgress: { completed: number; total: number } | null
  /** v38.2.3: ETA data from server for time remaining calculation */
  godModeEta?: {
    startedAt: number
    avgRunDurationMs?: number
  } | null
  maxRuns: number
  setMaxRuns: (n: number) => void
  handleStartGodMode: () => void
  handleStopGodMode: () => void
  setStep: (step: WizardStep) => void
  setGodModePath: (v: boolean) => void
}

// ── Constants ──────────────────────────────────────────────────────────────────

const RUN_OPTIONS = [10, 20, 30, 50] as const

/** Strategy label mapping for Russian display */
const STRATEGY_LABELS: Record<string, string> = {
  draw_range: 'Диапазон тиражей',
  batch_step: 'Размер батча',
  full_every: 'Полная ансамбль',
  cv_toggle: 'CV вкл/выкл',
  combined: 'Комбинированный',
  stability: 'Стабильность',
  // v38.2.3: New strategies
  deep_training: 'Глубокое обучение',
  seed_variation: 'Вариация seed',
  precision: 'Точность',
}

/** Strategy color mapping */
const STRATEGY_COLORS: Record<string, string> = {
  draw_range: 'bg-blue-500/15 text-blue-300 border-blue-500/20',
  batch_step: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
  full_every: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/20',
  cv_toggle: 'bg-amber-500/15 text-amber-300 border-amber-500/20',
  combined: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/20',
  stability: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20',
  // v38.2.3: New strategies
  deep_training: 'bg-rose-500/15 text-rose-300 border-rose-500/20',
  seed_variation: 'bg-teal-500/15 text-teal-300 border-teal-500/20',
  precision: 'bg-sky-500/15 text-sky-300 border-sky-500/20',
}

// ── Helper: concise param summary ─────────────────────────────────────────────

function paramsSummary(params: Record<string, unknown>): string {
  return Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
    .join(', ')
    .slice(0, 120)
}

// ── Helper: format consensus as percentage ─────────────────────────────────────

function fmtConsensus(val: number | undefined | null): string {
  if (val == null) return '—'
  return (val * 100).toFixed(1) + '%'
}

// ── Helper: median ─────────────────────────────────────────────────────────────

function median(arr: number[]): number {
  if (!arr.length) return 0
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

// ── Helper: confidence color classes ──────────────────────────────────────────

function confidenceColor(c: number): string {
  if (c >= 70) return 'from-emerald-500 to-green-400 shadow-emerald-500/25'
  if (c >= 50) return 'from-amber-500 to-yellow-400 shadow-amber-500/25'
  if (c >= 30) return 'from-orange-500 to-amber-400 shadow-orange-500/20'
  return 'from-slate-500 to-slate-400 shadow-slate-500/15'
}

function confidenceRing(c: number): string {
  if (c >= 70) return 'ring-2 ring-emerald-400/40'
  if (c >= 50) return 'ring-2 ring-amber-400/40'
  return ''
}

// ── Sub-components ────────────────────────────────────────────────────────────

function NumberBalls({
  numbers,
  gradient,
  size = 'lg',
}: {
  numbers: Array<{ number: string; [key: string]: unknown }>
  gradient: string
  size?: 'lg' | 'sm'
}) {
  const dim = size === 'lg' ? 'h-10 w-10 text-sm' : 'h-7 min-w-7 text-[10px]'
  return (
    <div className="flex flex-wrap gap-2">
      {numbers.map((n, i) => (
        <motion.div
          key={`${n.number}-${i}`}
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ delay: i * 0.05, type: 'spring', stiffness: 200 }}
          className={`${dim} rounded-full bg-gradient-to-br ${gradient} flex items-center justify-center shadow-lg`}
        >
          <span className="font-bold text-white">{n.number}</span>
        </motion.div>
      ))}
    </div>
  )
}

function RunPredictionBlock({ run, block, colorClass }: {
  run: GodModeResult['individual_runs'][number]
  block: 'block1' | 'block2'
  colorClass: string
}) {
  // v39.2.0: Guard against undefined prediction (failed/incomplete runs)
  const numbers = run.prediction?.[block]
  if (!numbers) return null
  return (
    <>
      {numbers.map((n, i) => (
        <span
          key={`run-${block}-${i}`}
          className={`inline-flex h-5 min-w-5 items-center justify-center rounded text-[9px] font-mono ${colorClass}`}
        >
          {n}
        </span>
      ))}
    </>
  )
}

// ── Component ──────────────────────────────────────────────────────────────────

export function StepGodMode({
  selectedGame,
  godModeLoading,
  godModeResult,
  godModeError,
  godModeProgress,
  godModeEta,
  maxRuns,
  setMaxRuns,
  handleStartGodMode,
  handleStopGodMode,
  setStep,
  setGodModePath,
}: StepGodModeProps) {
  const reducedMotion = usePrefersReducedMotion()
  const anim = reducedMotion ? fadeInInstant : fadeIn
  const [runsExpanded, setRunsExpanded] = useState(false)
  const [strategiesExpanded, setStrategiesExpanded] = useState(false)

  // v38.2.3 → v38.2.5: Live ETA timer — updates every second.
  // Uses a tick counter to force re-render every second; all time values
  // are computed as derived values (not stored in state). This avoids:
  //   1. React-hooks/refs violations (no ref updates during render)
  //   2. React-hooks/set-state-in-effect violations (no setState in useEffect)
  //   3. Timer flickering (useEffect depends only on isActive, not on
  //      godModeEta/godModeProgress which change on every poll)

  const [tick, setTick] = useState(0)

  const isActive = godModeLoading && !!godModeEta

  // Start/stop the 1-second tick based on active state only
  useEffect(() => {
    if (!isActive) return
    const timer = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(timer)
  }, [isActive])

  // Compute elapsed and ETA as derived values — no state, no refs needed
  const elapsedSeconds = isActive && godModeEta
    ? Math.floor((Date.now() - godModeEta.startedAt) / 1000)
    : 0

  const etaSeconds = useMemo(() => {
    if (!isActive || !godModeEta || !godModeProgress || godModeProgress.completed <= 0) return null
    const remaining = godModeProgress.total - godModeProgress.completed
    if (godModeEta.avgRunDurationMs) {
      return Math.ceil((remaining * godModeEta.avgRunDurationMs) / 1000)
    }
    if (elapsedSeconds > 0) {
      return Math.ceil(remaining * (elapsedSeconds / godModeProgress.completed))
    }
    return null
  }, [tick, isActive, godModeEta, godModeProgress, elapsedSeconds])

  // v38.2.3: Format seconds as human-readable time
  const formatTime = useCallback((seconds: number): string => {
    if (seconds < 60) return `${seconds}с`
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    if (m < 60) return s > 0 ? `${m}м ${s}с` : `${m}м`
    const h = Math.floor(m / 60)
    const rm = m % 60
    if (h < 24) return rm > 0 ? `${h}ч ${rm}м` : `${h}ч`
    const d = Math.floor(h / 24)
    const rh = h % 24
    return rh > 0 ? `${d}д ${rh}ч` : `${d}д`
  }, [])

  // ── Computed: frequency bar data ───────────────────────────────────────────

  const freqB1 = useMemo(() => {
    if (!godModeResult) return []
    return Object.entries(godModeResult.frequency_b1)
      .map(([num, count]) => ({ num: Number(num), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 15)
  }, [godModeResult])

  const freqB2 = useMemo(() => {
    if (!godModeResult) return []
    return Object.entries(godModeResult.frequency_b2)
      .map(([num, count]) => ({ num: Number(num), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 15)
  }, [godModeResult])

  const maxFreqB1 = useMemo(() => Math.max(...freqB1.map((f) => f.count), 1), [freqB1])
  const maxFreqB2 = useMemo(() => Math.max(...freqB2.map((f) => f.count), 1), [freqB2])

  // ── Computed: consensus distribution stats ────────────────────────────────

  const consensusStats = useMemo(() => {
    if (!godModeResult?.consensus_distribution?.length) return null
    const dist = godModeResult.consensus_distribution
    const b1 = dist.map((d) => d.block1)
    const b2 = dist.map((d) => d.block2)
    return {
      b1: { min: Math.min(...b1), max: Math.max(...b1), med: median(b1) },
      b2: { min: Math.min(...b2), max: Math.max(...b2), med: median(b2) },
    }
  }, [godModeResult])

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <motion.div key="god-mode" {...anim}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 mb-4">
        <Button variant="ghost" size="sm" onClick={() => { setGodModePath(false); setStep(2) }} className="text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4 mr-1" /> ← Назад к Тиражам
        </Button>
        <h2 className="text-lg font-bold">
          <Shield className="h-5 w-5 inline-block mr-2 text-violet-400" />
          Режим Бога: {selectedGame.name}
        </h2>
      </div>

      {/* ── 1. Start Panel ─────────────────────────────────────────────── */}
      {!godModeResult && !godModeLoading && !godModeError && (
        <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
          <CardContent className="py-8 flex flex-col items-center gap-5">
            {/* Shield icon */}
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center shadow-lg shadow-violet-500/30">
              <Shield className="h-8 w-8 text-white" />
            </div>
            <div className="text-center">
              <p className="text-base font-bold text-white">Режим Бога — Мультизапуск с глубоким анализом</p>
              <div className="text-xs text-slate-400 mt-2 max-w-md space-y-1.5">
                <p>
                  Запускает десятки независимых предсказаний с различными параметрами
                  (размер обучающей выборки, batchSize, cross-validation, seed).
                </p>
                <p>
                  Затем анализирует все результаты и формирует итоговое предсказание
                  на основе консенсуса, confidence-score и мета-стратегий.
                </p>
                <p className="text-violet-400 font-medium">
                  Результат: более высокая согласованность и надёжность предсказания.
                </p>
              </div>
            </div>

            {/* Runs selector */}
            <div className="flex flex-col items-center gap-2">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">Количество запусков</p>
              <div className="flex gap-2">
                {RUN_OPTIONS.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setMaxRuns(n)}
                    className={`h-9 px-4 rounded-lg text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                      maxRuns === n
                        ? 'bg-violet-500/25 border border-violet-500/50 text-violet-300'
                        : 'bg-white/5 border border-white/10 text-slate-400 hover:bg-white/10 hover:text-slate-300'
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            {/* Start button */}
            <Button
              onClick={handleStartGodMode}
              className="h-12 px-8 bg-gradient-to-r from-violet-600 to-fuchsia-500 hover:from-violet-500 hover:to-fuchsia-400 text-white font-semibold shadow-lg shadow-violet-500/20"
            >
              <Play className="h-5 w-5 mr-2" />
              Запустить Режим Бога ({maxRuns} запусков)
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── 2. Loading Panel ───────────────────────────────────────────── */}
      {godModeLoading && (
        <Card role="status" aria-live="polite" className="border-violet-500/30 bg-violet-500/5">
          <CardContent className="py-8 flex flex-col items-center gap-4">
            <Loader2 className="h-10 w-10 text-violet-400 animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium text-violet-300">Мультизапуск анализов...</p>
              <p className="text-xs text-slate-400 mt-1">
                Варьирование параметров для максимальной надёжности
              </p>
            </div>

            {godModeProgress && (
              <div className="w-full max-w-xs space-y-2">
                <Progress
                  value={godModeProgress.total > 0 ? (godModeProgress.completed / godModeProgress.total) * 100 : 0}
                  className="h-2 bg-white/10"
                />
                <div className="flex items-center justify-between text-[10px] text-slate-500">
                  <span>{godModeProgress.completed} / {godModeProgress.total} запусков</span>
                  {etaSeconds !== null && etaSeconds > 0 && (
                    <span className="text-violet-400 font-medium">~{formatTime(etaSeconds)} осталось</span>
                  )}
                </div>
                {elapsedSeconds > 0 && (
                  <p className="text-[10px] text-slate-600 text-center">
                    Прошло: {formatTime(elapsedSeconds)}
                    {etaSeconds !== null && etaSeconds > 0 && (
                      <span className="ml-2">
                        · Завершение ориентировочно в {(() => {
                          const now = new Date()
                          now.setSeconds(now.getSeconds() + etaSeconds)
                          return now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
                        })()}
                      </span>
                    )}
                  </p>
                )}
              </div>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={handleStopGodMode}
              className="border-red-500/30 text-red-400 hover:bg-red-500/10"
            >
              <Square className="h-4 w-4 mr-1" /> Отменить
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── 3. Error Panel ─────────────────────────────────────────────── */}
      {godModeError && (
        <Card role="status" aria-live="polite" className="border-red-500/30 bg-red-500/5">
          <CardContent className="py-6 flex flex-col items-center gap-3">
            <AlertTriangle className="h-8 w-8 text-red-400" />
            <p className="text-sm text-red-400 whitespace-pre-line text-center max-w-lg">{godModeError}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleStartGodMode}
              className="border-red-500/30 text-red-400 hover:bg-red-500/10"
            >
              <Zap className="h-4 w-4 mr-1" /> Повторить
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── 4. Results Panel ───────────────────────────────────────────── */}
      {godModeResult && godModeResult.status === 'ok' && (
        <motion.div className="space-y-4" {...anim}>
          {/* ── Summary Card ──────────────────────────────────────────── */}
          <Card className="border-violet-500/30 bg-gradient-to-br from-violet-500/10 via-fuchsia-500/5 to-transparent overflow-hidden relative">
            <div className="absolute top-0 right-0 w-40 h-40 bg-violet-500/5 rounded-full blur-3xl" />
            <CardHeader className="pb-3 relative">
              <CardTitle className="text-sm flex items-center gap-2">
                <Shield className="h-4 w-4 text-violet-400" />
                Результаты Режима Бога
                <Badge variant="outline" className="text-[10px] border-violet-500/30 text-violet-400 ml-auto">
                  {(() => { try { const gf = JSON.parse(godModeResult.game_format || '{}'); return `${gf.pick_b1 || '?'}x${gf.pick_b2 || '?'}` } catch { return godModeResult.game_format || '' } })()}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="relative">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-lg bg-white/5 p-3 text-center">
                  <div className="text-[10px] text-slate-400 mb-1">Всего запусков</div>
                  <div className="text-lg font-bold text-white">{godModeResult.runs_total}</div>
                </div>
                <div className="rounded-lg bg-white/5 p-3 text-center">
                  <div className="text-[10px] text-slate-400 mb-1">Ошибок</div>
                  <div className={`text-lg font-bold ${godModeResult.runs_failed > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                    {godModeResult.runs_failed}
                  </div>
                </div>
                <div className="rounded-lg bg-white/5 p-3 text-center">
                  <div className="text-[10px] text-slate-400 mb-1">Согласие Б1 (ср.)</div>
                  <div className="text-lg font-bold text-blue-400">{fmtConsensus(godModeResult.avg_consensus_b1)}</div>
                </div>
                <div className="rounded-lg bg-white/5 p-3 text-center">
                  <div className="text-[10px] text-slate-400 mb-1">Согласие Б2 (ср.)</div>
                  <div className="text-lg font-bold text-emerald-400">{fmtConsensus(godModeResult.avg_consensus_b2)}</div>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 mt-2">
                Данные: {godModeResult.total_draws} тиражей · {godModeResult.runs_total - godModeResult.runs_failed} успешных анализов
              </p>
              {/* ── Prediction Info ──────────────────────────────────── */}
              {godModeResult.predictionInfo && (
                <div className="flex items-center gap-4 flex-wrap text-xs mt-2 pt-2 border-t border-white/5">
                  <div className="flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-cyan-400" />
                    <span className="text-slate-400">Данные:</span>
                    <span className="font-mono text-cyan-300 font-semibold">
                      {godModeResult.predictionInfo.total_draws_used.toLocaleString()} тиражей
                    </span>
                    {godModeResult.predictionInfo.draw_range && (
                      <span className="text-slate-500 ml-1">
                        (№ {godModeResult.predictionInfo.draw_range})
                      </span>
                    )}
                  </div>
                  {godModeResult.predictionInfo.next_draw_no != null && (
                    <div className="flex items-center gap-1.5">
                      <Crosshair className="h-3.5 w-3.5 text-amber-400" />
                      <span className="text-slate-400">Предсказание для тиража:</span>
                      <span className="font-mono text-amber-300 font-semibold">
                        №{godModeResult.predictionInfo.next_draw_no}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Final Prediction Card ────────────────────────────────── */}
          {(() => {
            const fmtKey = selectedGame.key || ''
            const fmt = GAME_FORMATS[fmtKey]
            const pickB1 = fmt?.pick_b1 ?? 4
            const pickB2 = fmt?.pick_b2 ?? 4
            const finalB1 = godModeResult.top_numbers_b1.slice(0, pickB1)
            const finalB2 = pickB2 > 0 ? godModeResult.top_numbers_b2.slice(0, pickB2) : []
            return (
              <Card className="border-violet-500/30 bg-gradient-to-br from-violet-500/10 via-fuchsia-500/5 to-transparent overflow-hidden relative">
                <div className="absolute bottom-0 left-0 w-40 h-40 bg-fuchsia-500/5 rounded-full blur-3xl" />
                <CardHeader className="pb-3 relative">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Target className="h-4 w-4 text-violet-400" />
                    🎯 Итоговое предсказание
                  </CardTitle>
                </CardHeader>
                <CardContent className="relative space-y-4">
                  {/* Block 1 */}
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gradient-to-r from-blue-500 to-cyan-400 text-white">Блок 1</span>
                      <span className="text-[10px] text-slate-500">{pickB1} чисел</span>
                    </div>
                    <NumberBalls
                      numbers={finalB1}
                      gradient="from-blue-500 to-cyan-400 shadow-blue-500/30"
                      size="lg"
                    />
                  </div>
                  {/* Block 2 (only if applicable) */}
                  {pickB2 > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gradient-to-r from-emerald-500 to-teal-400 text-white">Блок 2</span>
                        <span className="text-[10px] text-slate-500">{pickB2} чисел</span>
                      </div>
                      <NumberBalls
                        numbers={finalB2}
                        gradient="from-emerald-500 to-teal-400 shadow-emerald-500/30"
                        size="lg"
                      />
                    </div>
                  )}
                  {/* Agreement stats */}
                  <div className="flex items-center gap-3 pt-2 border-t border-white/10">
                    <span className="text-[10px] text-slate-400">Согласие:</span>
                    <span className="text-xs font-mono text-blue-400">{fmtConsensus(godModeResult.avg_consensus_b1)} (Б1)</span>
                    {pickB2 > 0 && (
                      <>
                        <span className="text-[10px] text-slate-500">·</span>
                        <span className="text-xs font-mono text-emerald-400">{fmtConsensus(godModeResult.avg_consensus_b2)} (Б2)</span>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })()}

          {/* ── Confidence Scores Card ────────────────────────────────── */}
          {godModeResult.confidence_b1 && godModeResult.confidence_b1.length > 0 && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Gauge className="h-4 w-4 text-emerald-400" />
                  Уверенность по числам
                  <span className="text-[10px] text-slate-500 ml-auto">0–100%</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Block 1 confidence */}
                <div>
                  <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 1</p>
                  <div className="flex flex-wrap gap-2">
                    {godModeResult.confidence_b1.slice(0, 10).map((entry) => (
                      <div
                        key={`conf-b1-${entry.number}`}
                        className={`relative flex flex-col items-center ${confidenceRing(entry.confidence)}`}
                        title={`Число ${entry.number}: уверенность ${entry.confidence}%`}
                      >
                        <div className={`h-10 w-10 rounded-full bg-gradient-to-br ${confidenceColor(entry.confidence)} flex items-center justify-center`}>
                          <span className="text-sm font-bold text-white">{entry.number}</span>
                        </div>
                        <span className="text-[8px] text-slate-400 font-mono mt-0.5">{entry.confidence}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Block 2 confidence */}
                {godModeResult.confidence_b2 && godModeResult.confidence_b2.length > 0 && (
                <div>
                  <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 2</p>
                  <div className="flex flex-wrap gap-2">
                    {godModeResult.confidence_b2.slice(0, 10).map((entry) => (
                      <div
                        key={`conf-b2-${entry.number}`}
                        className={`relative flex flex-col items-center ${confidenceRing(entry.confidence)}`}
                        title={`Число ${entry.number}: уверенность ${entry.confidence}%`}
                      >
                        <div className={`h-10 w-10 rounded-full bg-gradient-to-br ${confidenceColor(entry.confidence)} flex items-center justify-center`}>
                          <span className="text-sm font-bold text-white">{entry.number}</span>
                        </div>
                        <span className="text-[8px] text-slate-400 font-mono mt-0.5">{entry.confidence}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                )}
                {/* Legend */}
                <div className="flex items-center gap-3 pt-1">
                  <span className="text-[9px] text-emerald-400">● 70%+ высокая</span>
                  <span className="text-[9px] text-amber-400">● 50–69% средняя</span>
                  <span className="text-[9px] text-orange-400">● 30–49% низкая</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ── Meta-Consensus Card ───────────────────────────────────── */}
          {(godModeResult.meta_consensus_b1?.length ?? 0) > 0 && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Layers className="h-4 w-4 text-cyan-400" />
                  Мета-консенсус
                  <span className="text-[10px] text-slate-500 ml-auto">числа из ≥3 стратегий</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Block 1 meta-consensus */}
                {godModeResult.meta_consensus_b1 && godModeResult.meta_consensus_b1.length > 0 && (
                  <div>
                    <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 1</p>
                    <div className="space-y-1.5">
                      {godModeResult.meta_consensus_b1.slice(0, 8).map((entry) => (
                        <div key={`meta-b1-${entry.number}`} className="flex items-center gap-2">
                          <span className="h-7 min-w-7 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-[10px] font-bold text-white shadow-sm">
                            {entry.number}
                          </span>
                          <div className="flex items-center gap-1 flex-wrap">
                            <span className="text-[9px] text-slate-500 mr-1">{entry.strategyCount} стр.</span>
                            {entry.strategies.map((s) => (
                              <Badge
                                key={s}
                                variant="outline"
                                className={`text-[8px] px-1.5 py-0 h-4 border ${STRATEGY_COLORS[s] || 'bg-white/5 text-slate-400 border-white/10'}`}
                              >
                                {STRATEGY_LABELS[s] || s}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Block 2 meta-consensus */}
                {godModeResult.meta_consensus_b2 && godModeResult.meta_consensus_b2.length > 0 && (
                  <div>
                    <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 2</p>
                    <div className="space-y-1.5">
                      {godModeResult.meta_consensus_b2.slice(0, 8).map((entry) => (
                        <div key={`meta-b2-${entry.number}`} className="flex items-center gap-2">
                          <span className="h-7 min-w-7 rounded-full bg-gradient-to-br from-emerald-500 to-teal-400 flex items-center justify-center text-[10px] font-bold text-white shadow-sm">
                            {entry.number}
                          </span>
                          <div className="flex items-center gap-1 flex-wrap">
                            <span className="text-[9px] text-slate-500 mr-1">{entry.strategyCount} стр.</span>
                            {entry.strategies.map((s) => (
                              <Badge
                                key={s}
                                variant="outline"
                                className={`text-[8px] px-1.5 py-0 h-4 border ${STRATEGY_COLORS[s] || 'bg-white/5 text-slate-400 border-white/10'}`}
                              >
                                {STRATEGY_LABELS[s] || s}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* ── Top Numbers Card (frequency + ranked) ──────────────────── */}
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Target className="h-4 w-4 text-blue-400" />
                Топ чисел по частоте
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Block 1 */}
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 1 — Топ числа</p>
                <NumberBalls
                  numbers={godModeResult.top_numbers_b1.slice(0, 8)}
                  gradient="from-blue-500 to-cyan-400 shadow-blue-500/20"
                />
              </div>
              {/* Block 2 - only if applicable */}
              {(() => {
                const fmt = GAME_FORMATS[selectedGame.key || '']
                return fmt && fmt.pick_b2 > 0
              })() && (
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 2 — Топ числа</p>
                <NumberBalls
                  numbers={godModeResult.top_numbers_b2.slice(0, 8)}
                  gradient="from-emerald-500 to-teal-400 shadow-emerald-500/20"
                />
              </div>
              )}
            </CardContent>
          </Card>

          {/* ── Frequency Heatmap ─────────────────────────────────────── */}
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-amber-400" />
                Частотная карта (топ 15)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Block 1 freq */}
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 1</p>
                <div className="overflow-x-auto max-w-full">
                  <div className="flex items-end gap-1 min-w-fit" style={{ height: '120px' }}>
                    {freqB1.map(({ num, count }) => {
                      const pct = maxFreqB1 > 0 ? (count / maxFreqB1) * 100 : 0
                      const intensity = count / maxFreqB1
                      const barColor =
                        intensity > 0.7
                          ? 'bg-blue-400'
                          : intensity > 0.4
                            ? 'bg-blue-500/70'
                            : 'bg-blue-500/40'
                      return (
                        <div key={num} className="flex flex-col items-center gap-1" style={{ width: '28px' }}>
                          <span className="text-[9px] text-slate-400 font-mono">{count}</span>
                          <div
                            className={`w-5 rounded-t-sm ${barColor} transition-all`}
                            style={{ height: `${Math.max(4, (pct / 100) * 80)}px` }}
                            title={`Число ${num}: ${count} раз`}
                          />
                          <span className="text-[9px] text-slate-400 font-mono">{num}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* Block 2 freq */}
              <div>
                <p className="text-[10px] text-slate-400 mb-2 font-medium uppercase tracking-wider">Блок 2</p>
                <div className="overflow-x-auto max-w-full">
                  <div className="flex items-end gap-1 min-w-fit" style={{ height: '120px' }}>
                    {freqB2.map(({ num, count }) => {
                      const pct = maxFreqB2 > 0 ? (count / maxFreqB2) * 100 : 0
                      const intensity = count / maxFreqB2
                      const barColor =
                        intensity > 0.7
                          ? 'bg-emerald-400'
                          : intensity > 0.4
                            ? 'bg-emerald-500/70'
                            : 'bg-emerald-500/40'
                      return (
                        <div key={num} className="flex flex-col items-center gap-1" style={{ width: '28px' }}>
                          <span className="text-[9px] text-slate-400 font-mono">{count}</span>
                          <div
                            className={`w-5 rounded-t-sm ${barColor} transition-all`}
                            style={{ height: `${Math.max(4, (pct / 100) * 80)}px` }}
                            title={`Число ${num}: ${count} раз`}
                          />
                          <span className="text-[9px] text-slate-400 font-mono">{num}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ── Consensus Distribution Card ───────────────────────────── */}
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Hash className="h-4 w-4 text-cyan-400" />
                Распределение согласия
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                {/* Block 1 consensus gauge */}
                <div className="space-y-2">
                  <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Блок 1</p>
                  <div className="rounded-lg bg-white/5 p-3 text-center">
                    <div className="text-2xl font-bold text-blue-400">{fmtConsensus(godModeResult.avg_consensus_b1)}</div>
                    <p className="text-[10px] text-slate-500 mt-1">среднее согласие</p>
                  </div>
                  <Progress value={(godModeResult.avg_consensus_b1 ?? 0) * 100} className="h-1.5 bg-white/10" />
                </div>
                {/* Block 2 consensus gauge */}
                <div className="space-y-2">
                  <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Блок 2</p>
                  <div className="rounded-lg bg-white/5 p-3 text-center">
                    <div className="text-2xl font-bold text-emerald-400">{fmtConsensus(godModeResult.avg_consensus_b2)}</div>
                    <p className="text-[10px] text-slate-500 mt-1">среднее согласие</p>
                  </div>
                  <Progress value={(godModeResult.avg_consensus_b2 ?? 0) * 100} className="h-1.5 bg-white/10" />
                </div>
              </div>

              {/* Distribution stats */}
              {consensusStats && (
                <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-white/5">
                  <div className="text-[10px] text-slate-400 space-y-1">
                    <p className="font-medium text-slate-300 mb-1">Блок 1 статистика</p>
                    <div className="flex justify-between"><span>Мин:</span><span className="font-mono text-slate-300">{fmtConsensus(consensusStats.b1.min)}</span></div>
                    <div className="flex justify-between"><span>Макс:</span><span className="font-mono text-slate-300">{fmtConsensus(consensusStats.b1.max)}</span></div>
                    <div className="flex justify-between"><span>Медиана:</span><span className="font-mono text-slate-300">{fmtConsensus(consensusStats.b1.med)}</span></div>
                  </div>
                  <div className="text-[10px] text-slate-400 space-y-1">
                    <p className="font-medium text-slate-300 mb-1">Блок 2 статистика</p>
                    <div className="flex justify-between"><span>Мин:</span><span className="font-mono text-slate-300">{fmtConsensus(consensusStats.b2.min)}</span></div>
                    <div className="flex justify-between"><span>Макс:</span><span className="font-mono text-slate-300">{fmtConsensus(consensusStats.b2.max)}</span></div>
                    <div className="flex justify-between"><span>Медиана:</span><span className="font-mono text-slate-300">{fmtConsensus(consensusStats.b2.med)}</span></div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Best vs Worst vs Accuracy Run ─────────────────────────── */}
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Trophy className="h-4 w-4 text-amber-400" />
                Сравнение запусков
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Best run */}
                {godModeResult.best_run ? (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Trophy className="h-4 w-4 text-emerald-400" />
                    <span className="text-xs font-bold text-emerald-400">Лучший (согласие)</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Согласие Б1</span>
                    <span className="font-mono text-emerald-400">{fmtConsensus(godModeResult.best_run?.consensus_strength?.block1)}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Согласие Б2</span>
                    <span className="font-mono text-emerald-400">{fmtConsensus(godModeResult.best_run?.consensus_strength?.block2)}</span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[9px] text-slate-500 font-mono leading-relaxed break-all">
                      {paramsSummary(godModeResult.best_run.params)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <RunPredictionBlock run={godModeResult.best_run} block="block1" colorClass="bg-blue-500/15 text-blue-300" />
                    <RunPredictionBlock run={godModeResult.best_run} block="block2" colorClass="bg-emerald-500/15 text-emerald-300" />
                  </div>
                </div>
                ) : (
                <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-center">
                  <p className="text-xs text-slate-500">Нет данных (все запуски с ошибкой)</p>
                </div>
                )}

                {/* Worst run */}
                {godModeResult.worst_run ? (
                <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <TrendingDown className="h-4 w-4 text-red-400" />
                    <span className="text-xs font-bold text-red-400">Худший запуск</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Согласие Б1</span>
                    <span className="font-mono text-red-400">{fmtConsensus(godModeResult.worst_run?.consensus_strength?.block1)}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Согласие Б2</span>
                    <span className="font-mono text-red-400">{fmtConsensus(godModeResult.worst_run?.consensus_strength?.block2)}</span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[9px] text-slate-500 font-mono leading-relaxed break-all">
                      {paramsSummary(godModeResult.worst_run.params)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <RunPredictionBlock run={godModeResult.worst_run} block="block1" colorClass="bg-white/10 text-slate-400 border border-white/10" />
                    <RunPredictionBlock run={godModeResult.worst_run} block="block2" colorClass="bg-white/10 text-slate-400 border border-white/10" />
                  </div>
                </div>
                ) : (
                <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-center">
                  <p className="text-xs text-slate-500">Нет данных</p>
                </div>
                )}
              </div>

              {/* Best accuracy run */}
              {godModeResult.best_accuracy_run && (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 space-y-3 mt-4">
                  <div className="flex items-center gap-2">
                    <Medal className="h-4 w-4 text-amber-400" />
                    <span className="text-xs font-bold text-amber-400">Лучший по бэктесту</span>
                    {godModeResult.best_accuracy_run.accuracy && (
                      <Badge variant="outline" className="text-[9px] border-amber-500/30 text-amber-400 ml-auto">
                        {godModeResult.best_accuracy_run.accuracy.last_50_avg.toFixed(2)} / {godModeResult.best_accuracy_run.accuracy.baseline_random.toFixed(1)} baseline
                      </Badge>
                    )}
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Согласие Б1</span>
                    <span className="font-mono text-amber-400">{fmtConsensus(godModeResult.best_accuracy_run.consensus_strength.block1)}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Согласие Б2</span>
                    <span className="font-mono text-amber-400">{fmtConsensus(godModeResult.best_accuracy_run.consensus_strength.block2)}</span>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[9px] text-slate-500 font-mono leading-relaxed break-all">
                      {paramsSummary(godModeResult.best_accuracy_run.params)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <RunPredictionBlock run={godModeResult.best_accuracy_run} block="block1" colorClass="bg-amber-500/15 text-amber-300" />
                    <RunPredictionBlock run={godModeResult.best_accuracy_run} block="block2" colorClass="bg-amber-500/15 text-amber-300" />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Strategy Stats Card (collapsible) ──────────────────────── */}
          {godModeResult.strategy_stats && godModeResult.strategy_stats.length > 0 && (
            <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
              <CardHeader className="pb-2">
                <button
                  type="button"
                  onClick={() => setStrategiesExpanded(!strategiesExpanded)}
                  className="w-full flex items-center justify-between text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded"
                >
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Layers className="h-4 w-4 text-violet-400" />
                    Стратегии ({godModeResult.strategy_stats.length})
                  </CardTitle>
                  {strategiesExpanded
                    ? <ChevronUp className="h-4 w-4 text-slate-400" />
                    : <ChevronDown className="h-4 w-4 text-slate-400" />
                  }
                </button>
              </CardHeader>
              {strategiesExpanded && (
                <CardContent>
                  <div className="max-h-72 overflow-y-auto rounded-lg border border-white/5">
                    <table className="w-full text-left">
                      <thead className="sticky top-0 bg-slate-950 z-10">
                        <tr className="text-[10px] text-slate-500 uppercase tracking-wider">
                          <th className="px-2 py-1.5 font-medium">Стратегия</th>
                          <th className="px-2 py-1.5 font-medium text-center">Запусков</th>
                          <th className="px-2 py-1.5 font-medium text-center">Согл. Б1</th>
                          <th className="px-2 py-1.5 font-medium text-center">Согл. Б2</th>
                          <th className="px-2 py-1.5 font-medium text-center">Точн.</th>
                          <th className="px-2 py-1.5 font-medium text-center">Δ vs random</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {godModeResult.strategy_stats.map((st) => {
                          const impColor = st.avg_improvement > 5
                            ? 'text-emerald-400'
                            : st.avg_improvement > 0
                              ? 'text-amber-400'
                              : 'text-red-400'
                          return (
                            <tr key={st.strategy} className="hover:bg-white/5 transition-colors">
                              <td className="px-2 py-2 text-[10px]">
                                <Badge
                                  variant="outline"
                                  className={`text-[9px] border ${STRATEGY_COLORS[st.strategy] || 'bg-white/5 text-slate-400 border-white/10'}`}
                                >
                                  {STRATEGY_LABELS[st.strategy] || st.strategy}
                                </Badge>
                              </td>
                              <td className="px-2 py-2 text-[10px] text-slate-300 text-center font-mono">{st.count}</td>
                              <td className="px-2 py-2 text-[10px] text-blue-400 text-center font-mono">{fmtConsensus(st.avg_consensus_b1)}</td>
                              <td className="px-2 py-2 text-[10px] text-emerald-400 text-center font-mono">{fmtConsensus(st.avg_consensus_b2)}</td>
                              <td className="px-2 py-2 text-[10px] text-amber-400 text-center font-mono">{st.avg_accuracy.toFixed(2)}</td>
                              <td className={`px-2 py-2 text-[10px] text-center font-mono ${impColor}`}>
                                {st.avg_improvement > 0 ? '+' : ''}{st.avg_improvement.toFixed(1)}%
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          {/* ── Individual Runs Table (collapsible) ───────────────────── */}
          <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
            <CardHeader className="pb-2">
              <button
                type="button"
                onClick={() => setRunsExpanded(!runsExpanded)}
                className="w-full flex items-center justify-between text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded"
              >
                <CardTitle className="text-sm flex items-center gap-2">
                  <Hash className="h-4 w-4 text-violet-400" />
                  Все запуски ({godModeResult.individual_runs.length})
                </CardTitle>
                {runsExpanded
                  ? <ChevronUp className="h-4 w-4 text-slate-400" />
                  : <ChevronDown className="h-4 w-4 text-slate-400" />
                }
              </button>
            </CardHeader>
            {runsExpanded && (
              <CardContent>
                <div className="max-h-96 overflow-y-auto overflow-x-auto rounded-lg border border-white/5">
                  <table className="w-full text-left">
                    <thead className="sticky top-0 bg-slate-950 z-10">
                      <tr className="text-[10px] text-slate-500 uppercase tracking-wider">
                        <th className="px-2 py-1.5 font-medium">#</th>
                        <th className="px-2 py-1.5 font-medium">Стратегия</th>
                        <th className="px-2 py-1.5 font-medium">Параметры</th>
                        <th className="px-2 py-1.5 font-medium">Прогноз</th>
                        <th className="px-2 py-1.5 font-medium text-center">Согл.</th>
                        <th className="px-2 py-1.5 font-medium text-center">Бэктест</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {godModeResult.individual_runs.map((run, idx) => {
                        const bt = run.backtest as Record<string, number> | null
                        const btScore = bt?.last_50_avg ?? bt?.backtest_avg_50 ?? bt?.avg_hits ?? null
                        const strategy = (run.params as Record<string, unknown>).strategy as string | undefined
                        return (
                          <tr key={idx} className={run.error ? 'bg-red-500/5' : 'hover:bg-white/[0.02] transition-colors'}>
                            <td className="px-2 py-1.5 text-[10px] text-slate-500 font-mono w-6">{idx + 1}</td>
                            <td className="px-2 py-1.5">
                              {strategy && (
                                <Badge
                                  variant="outline"
                                  className={`text-[8px] px-1 py-0 h-4 border whitespace-nowrap ${STRATEGY_COLORS[strategy] || 'bg-white/5 text-slate-400 border-white/10'}`}
                                >
                                  {STRATEGY_LABELS[strategy] || strategy}
                                </Badge>
                              )}
                            </td>
                            <td className="px-2 py-1.5 text-[10px] text-slate-400 font-mono max-w-[140px] truncate" title={paramsSummary(run.params)}>
                              {run.error ? (
                                <span className="text-red-400">{run.error}</span>
                              ) : (
                                paramsSummary(run.params)
                              )}
                            </td>
                            {!run.error && (
                            <td className="px-2 py-1.5">
                              <div className="flex flex-wrap gap-0.5 max-w-[200px]">
                                <RunPredictionBlock run={run} block="block1" colorClass="bg-blue-500/15 text-blue-300" />
                                {run.prediction.block2.length > 0 && (
                                  <span className="text-slate-600 text-[9px] self-center mx-px">+</span>
                                )}
                                <RunPredictionBlock run={run} block="block2" colorClass="bg-emerald-500/15 text-emerald-300" />
                              </div>
                            </td>
                            )}
                            {run.error && (
                            <td className="px-2 py-1.5">
                              <span className="text-[10px] text-slate-600">—</span>
                            </td>
                            )}
                            <td className="px-2 py-1.5 text-center">
                              <span className="text-[10px] font-mono text-slate-300">
                                {run.consensus_strength
                                  ? `${fmtConsensus(run.consensus_strength.block1)} / ${fmtConsensus(run.consensus_strength.block2)}`
                                  : '—'
                                }
                              </span>
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              {btScore != null ? (
                                <span className="text-[10px] font-mono text-amber-400">{btScore.toFixed(2)}</span>
                              ) : bt ? (
                                <span className="text-[9px] text-slate-500">—</span>
                              ) : (
                                <span className="text-[9px] text-slate-500">—</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            )}
          </Card>

          {/* ── Run Again ─────────────────────────────────────────────── */}
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              onClick={() => {
                handleStartGodMode()
              }}
              className="border-violet-500/30 text-violet-400 hover:bg-violet-500/10"
            >
              <Zap className="h-4 w-4 mr-1" /> Запустить ещё раз
            </Button>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
