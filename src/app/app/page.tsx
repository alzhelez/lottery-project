'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Brain, Target, Zap, Download, CheckCircle2, AlertTriangle,
  ArrowLeft, ArrowRight, Loader2, Dice1, Dice2, Dice3, Dice4, Dice5,
  Sparkles, RefreshCw, ChevronRight, TrendingUp, BarChart3, Activity,
  Shield, Eye, Layers, Flame, Snowflake, GitBranch, FileText, Terminal,
  Copy, Check
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

// ── Types ────────────────────────────────────────────────────────────────────

interface GameAnalysis {
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
}

interface GameCategories {
  high: GameAnalysis[]
  moderate: GameAnalysis[]
  normal: GameAnalysis[]
  insufficient: GameAnalysis[]
}

interface PredictionResult {
  status: string
  game_format: string
  game_key?: string
  total_draws: number
  prediction: {
    block1: number[]
    block2: number[]
    block1_methods?: number[][]
    block2_methods?: number[][]
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
}

interface PipelineResult {
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
  }
  std_prediction: {
    block1: number[]
    block2: number[]
  }
  rng_prediction: {
    block1: number[]
    block2: number[]
  }
  position_analysis: {
    block1: Record<string, unknown>
    block2: Record<string, unknown>
  }
  individual_predictions: { block1: number[]; block2: number[] }[]
  error?: string
}

type WizardStep = 1 | 2 | 3 | 4

// ── Constants ────────────────────────────────────────────────────────────────

const GAME_ICONS: Record<string, typeof Dice1> = {
  '4x20': Dice1,
  '6x45plus': Dice2,
  '5x36plus': Dice3,
  '5x2': Dice4,
  'keno2': Dice5,
}

// Game-specific gradient classes (used in prediction cards)
const GAME_GRADIENTS: Record<string, string> = {
  '4x20': 'from-blue-500 to-cyan-400',
  '6x45plus': 'from-emerald-500 to-teal-400',
  '5x36plus': 'from-sky-500 to-blue-400',
  '5x2': 'from-violet-500 to-purple-400',
 'keno2': 'from-orange-500 to-amber-400',
}

// Draw format descriptions for each game
const GAME_FORMATS: Record<string, { blocks: string; pick_b1: number; pick_b2: number; b1_range: string; b2_range: string; example: string }> = {
  '4x20': { blocks: '2 блока', pick_b1: 4, pick_b2: 4, b1_range: '1-20', b2_range: '1-20', example: '10.04.2026 15:30||13279||3,7,12,15,18||2,5,9,14' },
  '6x45plus': { blocks: '2 блока', pick_b1: 6, pick_b2: 1, b1_range: '1-45', b2_range: '1-4', example: '10.04.2026 10:00||5678||5,12,23,31,37,44||3' },
  '5x36plus': { blocks: '2 блока', pick_b1: 5, pick_b2: 1, b1_range: '1-36', b2_range: '1-4', example: '10.04.2026 22:30||4231||2,8,15,27,33||4' },
  '5x2': { blocks: '2 блока', pick_b1: 5, pick_b2: 2, b1_range: '1-50', b2_range: '1-10', example: '10.04.2026 21:30||1892||7,14,22,35,48||3,11' },
  'keno2': { blocks: '2 блока', pick_b1: 20, pick_b2: 1, b1_range: '1-80', b2_range: '1-10', example: '10.04.2026 12:00||1234||0,1,1,0,...(parity)...||3,7,12,...(20 nums)...||5' },
}

// ── Animation variants ───────────────────────────────────────────────────────

const fadeIn = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.3 },
}

const stagger = {
  animate: { transition: { staggerChildren: 0.08 } },
}

// ── Component ────────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard not available
    }
  }
  return (
    <button
      onClick={handleCopy}
      className="shrink-0 inline-flex items-center justify-center h-7 w-7 rounded-md hover:bg-white/10 transition-colors text-slate-500 hover:text-slate-300"
      title={copied ? 'Скопировано' : 'Копировать'}
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

export default function Home() {
  const [downloading, setDownloading] = useState(false)
  const [showSetup, setShowSetup] = useState(false)

  const handleDownloadProject = async () => {
    setDownloading(true)
    try {
      const res = await fetch('/api/download-project')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'lottery-project.tar.gz'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed:', err)
    } finally {
      setDownloading(false)
    }
  }

  const [step, setStep] = useState<WizardStep>(1)
  const [analyzeLoading, setAnalyzeLoading] = useState(true)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [games, setGames] = useState<GameAnalysis[]>([])
  const [categories, setCategories] = useState<GameCategories | null>(null)
  const [selectedGame, setSelectedGame] = useState<GameAnalysis | null>(null)

  const [fetchLoading, setFetchLoading] = useState(false)
  const [fetchDone, setFetchDone] = useState(false)
  const [fetchResult, setFetchResult] = useState<{ game: string; total_draws: number; data_file: string } | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const [predictLoading, setPredictLoading] = useState(false)
  const [predictResult, setPredictResult] = useState<PredictionResult | null>(null)
  const [predictError, setPredictError] = useState<string | null>(null)

  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null)
  const [pipelineError, setPipelineError] = useState<string | null>(null)

  // ── Step 1: Auto-analyze on mount ──────────────────────────────────────────

  const runAnalyze = useCallback(async () => {
    setAnalyzeLoading(true)
    setAnalyzeError(null)
    try {
      const res = await fetch('/api/lottery/analyze', { method: 'POST' })
      const data = await res.json()
      if (data.error) {
        const msg = data.hint ? `${data.error}\n${data.hint}` : data.error
        throw new Error(msg)
      }
      setGames(data.games || [])
      setCategories(data.categories || null)
      // Restore selected game if persisted
      if (typeof window !== 'undefined') {
        const saved = sessionStorage.getItem('lp_selected_game')
        if (saved && data.games) {
          const found = data.games.find((g: GameAnalysis) => g.key === saved || g.name === saved)
          if (found) setSelectedGame(found)
        }
      }
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : 'Ошибка анализа')
    } finally {
      setAnalyzeLoading(false)
    }
  }, [])

  useEffect(() => {
    runAnalyze()
  }, [runAnalyze])

  // ── Step 2: Fetch draws ────────────────────────────────────────────────────

  const handleFetchDraws = async () => {
    if (!selectedGame?.key) return
    setFetchLoading(true)
    setFetchError(null)
    setFetchDone(false)
    try {
      const res = await fetch('/api/lottery/fetch-draws', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key }),
      })
      const data = await res.json()
      if (!res.ok || data.error) {
        const msg = data.hint ? `${data.error || 'Ошибка'}\n${data.hint}` : (data.error || `Ошибка HTTP ${res.status}`)
        throw new Error(msg)
      }
      const totalDraws = typeof data.total_draws === 'number' ? data.total_draws : 0
      setFetchResult({ game: data.game || '', total_draws: totalDraws, data_file: data.data_file || '' })
      if (totalDraws > 0) {
        setFetchDone(true)
      } else {
        setFetchError('Не удалось загрузить тиражи для этой игры. Попробуйте другую игру.')
      }
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : 'Ошибка загрузки тиражей')
    } finally {
      setFetchLoading(false)
    }
  }

  // ── Step 3: Run predictions ────────────────────────────────────────────────

  const handlePredict = async () => {
    if (!selectedGame) return
    setPredictLoading(true)
    setPredictError(null)
    setPredictResult(null)
    try {
      const dataFile = fetchResult?.data_file || (selectedGame.key ? `/tmp/draws_${selectedGame.key}.txt` : '')
      const res = await fetch('/api/lottery/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key, data_file: dataFile }),
      })
      const raw = await res.json()
      if (raw.status === 'error') {
        const msg = raw.hint ? `${raw.error || 'Ошибка предсказания'}\n${raw.hint}` : (raw.error || 'Ошибка предсказания')
        throw new Error(msg)
      }

      // Adapt predict.py output to frontend format
      const acc = raw.accuracy || {}
      const mc = raw.monte_carlo || {}
      const cv = raw.cross_validation
      const votes_b1 = raw.prediction?.consensus_votes_b1 || {}
      const votes_b2 = raw.prediction?.consensus_votes_b2 || {}
      const topB1 = Math.max(...Object.values(votes_b1).map(Number), 0)
      const topB2 = Math.max(...Object.values(votes_b2).map(Number), 0)
      const totalB1 = Object.values(votes_b1).reduce((s, v) => s + Number(v), 0)
      const totalB2 = Object.values(votes_b2).reduce((s, v) => s + Number(v), 0)

      const data: PredictionResult = {
        status: raw.status,
        game_format: `${raw.game_format?.pick_b1 ?? '?'}/${raw.game_format?.pick_b2 ?? '?'}`,
        game_key: raw.game,
        total_draws: raw.data_quality?.total_draws ?? 0,
        prediction: {
          block1: raw.prediction?.block1 || [],
          block2: raw.prediction?.block2 || [],
          block1_methods: raw.analysis_methods?.map((m: string, i: number) => raw.prediction?.block1 || []) || [],
          block2_methods: raw.analysis_methods?.map((m: string, i: number) => raw.prediction?.block2 || []) || [],
        },
        consensus_strength: {
          block1: totalB1 > 0 ? topB1 / totalB1 : 0,
          block2: totalB2 > 0 ? topB2 / totalB2 : 0,
        },
        random_baseline: {
          block1: [],
          block2: [],
          expected_hits: acc.baseline_random ?? 0,
        },
        cross_validation: cv && !cv.error ? cv : {},
        backtest: acc.history_sample ? { last_50_avg: acc.last_50_avg, last_100_avg: acc.last_100_avg, last_200_avg: acc.last_200_avg, improvement_pct: acc.improvement_pct, baseline_random: acc.baseline_random } : {},
        monte_carlo: mc && mc.mean ? { iterations: 5000, expected_hits: mc.mean, ci_95_low: mc.p5, ci_95_high: mc.p95, p_ge_5: mc.p_ge5 } : {},
        models_used: raw.game_format?.total_models ?? 183,
        analysis_methods: raw.analysis_methods || [],
      }
      setPredictResult(data)
    } catch (err) {
      setPredictError(err instanceof Error ? err.message : 'Ошибка предсказания')
    } finally {
      setPredictLoading(false)
    }
  }

  // ── Step 4: Pipeline ──────────────────────────────────────────────────────

  const handlePipeline = async () => {
    if (!selectedGame) return
    setPipelineLoading(true)
    setPipelineError(null)
    setPipelineResult(null)
    try {
      const dataFile = fetchResult?.data_file || (selectedGame.key ? `/tmp/draws_${selectedGame.key}.txt` : '')
      const res = await fetch('/api/lottery/pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key, data_file: dataFile }),
      })
      const raw = await res.json()
      if (raw.status === 'error') {
        const msg = raw.hint ? `${raw.error || 'Ошибка pipeline'}\n${raw.hint}` : (raw.error || 'Ошибка pipeline')
        throw new Error(msg)
      }

      // Adapt pipeline.py output to frontend format
      const data: PipelineResult = {
        status: raw.status,
        game_key: raw.game || selectedGame.key,
        game_format: `${raw.pick_b1 ?? '?'}/${raw.pick_b2 ?? '?'}`,
        total_draws: raw.accuracy_entries ?? 0,
        runs_performed: 1,
        prediction: {
          block1: raw.final_prediction?.block1 || [],
          block2: raw.final_prediction?.block2 || [],
        },
        confidence: {
          block1: raw.confidence?.b1_score ?? 0,
          block2: raw.confidence?.b2_score ?? 0,
          overall: raw.confidence?.overall ?? 0,
        },
        std_prediction: raw.std_prediction || { block1: [], block2: [] },
        rng_prediction: raw.rng_prediction || { block1: [], block2: [] },
        position_analysis: {
          block1: raw.position_details?.b1 || raw.position_details?.block1 || {},
          block2: raw.position_details?.b2 || raw.position_details?.block2 || {},
        },
        individual_predictions: [],
      }
      setPipelineResult(data)
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : 'Ошибка pipeline')
    } finally {
      setPipelineLoading(false)
    }
  }

  // ── Game selection handler ─────────────────────────────────────────────────

  const handleSelectGame = (game: GameAnalysis) => {
    setSelectedGame(game)
    setStep(2)
    setFetchDone(false)
    setFetchResult(null)
    setFetchError(null)
    setPredictResult(null)
    setPredictError(null)
    setPipelineResult(null)
    setPipelineError(null)
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('lp_selected_game', game.key || game.name)
    }
  }

  // ── Render helpers ─────────────────────────────────────────────────────────

  const getScoreGradient = (score: number) => {
    if (score < 25) return 'from-emerald-500 to-emerald-400'
    if (score < 50) return 'from-amber-500 to-yellow-400'
    return 'from-red-500 to-rose-400'
  }

  const getVerdictBadge = (verdict: string, color: string) => {
    if (!color) {
      if (verdict.includes('ВЫСОКАЯ')) color = 'red'
      else if (verdict.includes('Умеренная')) color = 'yellow'
      else color = 'green'
    }
    const map: Record<string, string> = {
      green: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
      yellow: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      red: 'bg-red-500/20 text-red-400 border-red-500/30',
    }
    return map[color] || map.green
  }

  const CATEGORY_CONFIG = [
    { key: 'high' as const, label: '🔴 Высокая аномальность', desc: 'score ≥ 50 — наибольший потенциал', empty: 'Нет игр с высокой аномальностью', border: 'border-red-500/20' },
    { key: 'moderate' as const, label: '🟡 Умеренная аномальность', desc: 'score 25–49 — есть отклонения', empty: 'Нет игр с умеренной аномальностью', border: 'border-amber-500/20' },
    { key: 'normal' as const, label: '🟢 Статистически случайные', desc: 'score < 25 — близко к случайным', empty: 'Все игры показывают аномальность', border: 'border-emerald-500/20' },
    { key: 'insufficient' as const, label: '❓ Мало данных', desc: '< 10 тиражей — анализ ненадёжен', empty: 'Для всех игр достаточно данных', border: 'border-slate-500/20' },
  ]

  const getGamesForCategory = (key: string): GameAnalysis[] => {
    if (!categories) return games
    return categories[key as keyof GameCategories] || []
  }

  return (
    <div className="min-h-screen flex flex-col text-white">
      {/* Custom scrollbar for columns */}
      <style>{`
        .custom-scrollbar-column {
          scrollbar-width: thin;
          scrollbar-color: rgba(255,255,255,0.15) transparent;
        }
        .custom-scrollbar-column::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar-column::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar-column::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.15);
          border-radius: 2px;
        }
      `}</style>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-[#0a0f1e]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shrink-0">
            <Brain className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-bold text-white truncate">Локальный предсказатель</h1>
            <p className="text-[11px] text-slate-400">183 моделей · DualBayesRing · k-fold CV</p>
          </div>
          <Badge variant="outline" className="ml-auto border-blue-500/30 text-blue-400 text-xs shrink-0">
            <Shield className="h-3 w-3 mr-1" /> v22.0
          </Badge>
        </div>
      </header>

      {/* ── Step Indicator ──────────────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto w-full px-4 pt-4">
        <div className="flex items-center gap-1 sm:gap-2 overflow-x-auto pb-2">
          {[
            { n: 1, label: 'Анализ' },
            { n: 2, label: 'Тиражи' },
            { n: 3, label: 'Прогноз' },
            { n: 4, label: 'Pipeline' },
          ].map(({ n, label }, i) => {
            const isActive = step === n
            const isDone = step > n
            return (
              <div key={n} className="flex items-center shrink-0">
                {i > 0 && (
                  <div className={`w-6 sm:w-10 h-px ${isDone ? 'bg-blue-500' : 'bg-white/10'}`} />
                )}
                <button
                  onClick={() => {
                    if (n === 1) { setStep(1) }
                    else if (n === 2 && selectedGame) { setStep(2) }
                    else if (n === 3 && fetchDone) { setStep(3) }
                    else if (n === 4 && predictResult) { setStep(4) }
                  }}
                  disabled={
                    (n === 2 && !selectedGame) ||
                    (n === 3 && !fetchDone) ||
                    (n === 4 && !predictResult)
                  }
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                      : isDone
                        ? 'text-blue-400/70 hover:text-blue-300 cursor-pointer'
                        : 'text-slate-500 cursor-not-allowed'
                  }`}
                >
                  <div className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    isActive ? 'bg-blue-500 text-white' : isDone ? 'bg-blue-500/30 text-blue-400' : 'bg-white/10 text-slate-500'
                  }`}>
                    {isDone ? <CheckCircle2 className="h-3 w-3" /> : n}
                  </div>
                  <span className="hidden sm:inline">{label}</span>
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Main Content ────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-4">
        <AnimatePresence mode="wait">
          {/* ═══════════════════════════════════════════════════════════════ */}
          {/* STEP 1: Game Analysis                                         */}
          {/* ═══════════════════════════════════════════════════════════════ */}
          {step === 1 && (
            <motion.div key="step1" {...fadeIn}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-blue-400" />
                  <h2 className="text-lg font-bold">Анализ доступных игр</h2>
                </div>
                <Button variant="ghost" size="sm" onClick={runAnalyze} disabled={analyzeLoading} className="text-slate-400 hover:text-white">
                  <RefreshCw className={`h-4 w-4 mr-1 ${analyzeLoading ? 'animate-spin' : ''}`} />
                  Обновить
                </Button>
              </div>

              {analyzeLoading && (
                <div className="space-y-2">
                  {[1, 2, 3, 4, 5].map(i => (
                    <Skeleton key={i} className="h-8 w-full rounded-lg bg-white/10" />
                  ))}
                  <p className="text-center text-sm text-slate-400">
                    <Loader2 className="h-4 w-4 inline mr-2 animate-spin" />
                    Сканирование файлов тиражей...
                  </p>
                </div>
              )}

              {analyzeError && (
                <Card className="border-red-500/30 bg-red-500/5">
                  <CardContent className="py-6 flex flex-col items-center gap-3">
                    <AlertTriangle className="h-8 w-8 text-red-400" />
                    <p className="text-sm text-red-400 whitespace-pre-line">{analyzeError}</p>
                    <Button variant="outline" size="sm" onClick={runAnalyze} className="border-red-500/30 text-red-400">
                      <RefreshCw className="h-4 w-4 mr-1" /> Повторить
                    </Button>
                  </CardContent>
                </Card>
              )}

              {!analyzeLoading && !analyzeError && games.length === 0 && (
                <Card className="border-white/10 bg-white/5">
                  <CardContent className="py-8 text-center">
                    <Target className="h-10 w-10 text-slate-500 mx-auto mb-3" />
                    <p className="text-sm text-slate-400">Не удалось загрузить данные анализа</p>
                    <p className="text-xs text-slate-500 mt-1">Проверьте подключение к stoloto.ru API</p>
                  </CardContent>
                </Card>
              )}

              {!analyzeLoading && !analyzeError && games.length > 0 && (
                <>
                  {/* Summary bar */}
                  <div className="flex items-center justify-between mb-4 px-1">
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-slate-400">Всего игр: <span className="font-bold text-white">{games.length}</span></span>
                      {categories?.high && categories.high.length > 0 && (
                        <span className="text-red-400 font-medium">{categories.high.length} с высокой аномальностью</span>
                      )}
                      {categories?.moderate && categories.moderate.length > 0 && (
                        <span className="text-amber-400 font-medium">{categories.moderate.length} умеренных</span>
                      )}
                      {categories?.normal && categories.normal.length > 0 && (
                        <span className="text-emerald-400 font-medium">{categories.normal.length} случайных</span>
                      )}
                    </div>
                    <Badge variant="outline" className="border-blue-500/30 text-blue-400 text-[10px]">
                      <Activity className="h-3 w-3 mr-1" /> {games.filter(g => g.draws >= 10).length} проанализировано
                    </Badge>
                  </div>

                  {/* Three-column layout */}
                  {(() => {
                    const highGames = getGamesForCategory('high')
                    const moderateGames = getGamesForCategory('moderate')
                    const normalGames = getGamesForCategory('normal')
                    const insufficientGames = getGamesForCategory('insufficient')

                    // Reference height: high category count × ~44px per row + ~56px header
                    const refCount = highGames.length
                    const refHeight = 56 + refCount * 44

                    const columns: {
                      key: string; label: string; desc: string; empty: string;
                      borderColor: string; bgColor: string; badgeBg: string;
                      games: GameAnalysis[]; needsScroll: boolean
                    }[] = [
                      {
                        key: 'high',
                        label: '🔴 Высокая аномальность',
                        desc: 'score ≥ 50',
                        empty: 'Нет игр с высокой аномальностью',
                        borderColor: 'border-red-500/40',
                        bgColor: 'bg-red-500/[0.04]',
                        badgeBg: 'bg-red-500/20 text-red-400 border-red-500/30',
                        games: highGames,
                        needsScroll: false,
                      },
                      {
                        key: 'moderate',
                        label: '🟡 Умеренная аномальность',
                        desc: 'score 25–49',
                        empty: 'Нет игр с умеренной аномальностью',
                        borderColor: 'border-amber-500/40',
                        bgColor: 'bg-amber-500/[0.04]',
                        badgeBg: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
                        games: moderateGames,
                        needsScroll: moderateGames.length > refCount,
                      },
                      {
                        key: 'normal',
                        label: '🟢 Статистически случайные',
                        desc: 'score < 25',
                        empty: 'Все игры показывают аномальность',
                        borderColor: 'border-emerald-500/40',
                        bgColor: 'bg-emerald-500/[0.04]',
                        badgeBg: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
                        games: normalGames,
                        needsScroll: normalGames.length > refCount,
                      },
                    ]

                    return (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          {columns.map((col) => (
                            <div
                              key={col.key}
                              className={`rounded-xl border ${col.borderColor} ${col.bgColor} overflow-hidden flex flex-col`}
                            >
                              {/* Column header */}
                              <div className="px-3 py-2.5 border-b border-white/5 shrink-0">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="min-w-0">
                                    <p className="text-xs font-bold truncate">{col.label}</p>
                                    <p className="text-[10px] text-slate-500 mt-0.5">{col.desc}</p>
                                  </div>
                                  <Badge variant="outline" className={`text-[9px] shrink-0 ${col.badgeBg}`}>
                                    {col.games.length}
                                  </Badge>
                                </div>
                              </div>

                              {/* Column body */}
                              <div
                                className="flex-1 overflow-y-auto custom-scrollbar-column"
                                style={{ maxHeight: col.needsScroll ? `${refHeight}px` : undefined }}
                              >
                                {col.games.length === 0 ? (
                                  <p className="text-[11px] text-slate-500 text-center py-6 px-3">{col.empty}</p>
                                ) : (
                                  <motion.div
                                    className="flex flex-col gap-0.5 p-1.5"
                                    variants={stagger}
                                    initial="initial"
                                    animate="animate"
                                  >
                                    {col.games.map((game) => {
                                      const isSelected = selectedGame?.key === game.key
                                      return (
                                        <motion.div key={game.key || game.name} variants={fadeIn}>
                                          <button
                                            onClick={() => handleSelectGame(game)}
                                            className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md transition-all text-left ${
                                              isSelected
                                                ? 'bg-blue-500/15 border border-blue-500/30'
                                                : 'hover:bg-white/5 border border-transparent'
                                            }`}
                                          >
                                            <div className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: game.score >= 50 ? '#f87171' : game.score >= 25 ? '#fbbf24' : '#34d399' }} />
                                            <span className="text-[11px] font-medium truncate flex-1 min-w-0">{game.name}</span>
                                            <span className="text-[9px] text-slate-500 shrink-0">{game.draws}д</span>
                                            <span className={`text-[10px] font-mono font-bold w-5 text-right shrink-0 ${game.score < 25 ? 'text-emerald-400' : game.score >= 50 ? 'text-red-400' : 'text-amber-400'}`}>
                                              {Math.round(game.score)}
                                            </span>
                                          </button>
                                        </motion.div>
                                      )
                                    })}
                                  </motion.div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Insufficient data row (below columns) */}
                        {insufficientGames.length > 0 && (
                          <div className="mt-3 rounded-xl border border-slate-500/20 bg-slate-500/[0.04] overflow-hidden">
                            <div className="px-3 py-2 border-b border-white/5 flex items-center gap-2">
                              <span className="text-xs font-bold">❓ Мало данных</span>
                              <span className="text-[10px] text-slate-500">{'< 10 тиражей — анализ ненадёжен'}</span>
                              <Badge variant="outline" className="text-[9px] bg-slate-500/20 text-slate-400 border-slate-500/30">
                                {insufficientGames.length}
                              </Badge>
                            </div>
                            <div className="flex flex-wrap gap-1 p-2">
                              {insufficientGames.map((game) => {
                                const isSelected = selectedGame?.key === game.key
                                return (
                                  <button
                                    key={game.key || game.name}
                                    onClick={() => handleSelectGame(game)}
                                    className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-all ${
                                      isSelected
                                        ? 'bg-blue-500/15 border border-blue-500/30'
                                        : 'hover:bg-white/5 border border-white/5'
                                    }`}
                                  >
                                    <span className="text-slate-400">{game.name}</span>
                                    <span className="text-[9px] text-slate-500">{game.draws}д</span>
                                  </button>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </>
                    )
                  })()}
                  <p className="text-center text-xs text-slate-500 mt-6">
                    Нажмите на карточку игры, чтобы продолжить →
                  </p>
                </>
              )}
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════════════════════ */}
          {/* STEP 2: Draw Format + Fetch Draws                            */}
          {/* ═══════════════════════════════════════════════════════════════ */}
          {step === 2 && selectedGame && (
            <motion.div key="step2" {...fadeIn}>
              <div className="flex items-center gap-3 mb-4">
                <Button variant="ghost" size="sm" onClick={() => setStep(1)} className="text-slate-400 hover:text-white">
                  <ArrowLeft className="h-4 w-4 mr-1" /> Назад
                </Button>
                <div className="flex items-center gap-2">
                  {(() => { const I = GAME_ICONS[selectedGame.key || ''] || Dice1; return <I className="h-5 w-5 text-blue-400" /> })()}
                  <h2 className="text-lg font-bold">{selectedGame.name}</h2>
                </div>
              </div>

              {/* Game Info Card */}
              <Card className="border-white/10 bg-white/5 backdrop-blur-sm mb-4">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Layers className="h-4 w-4 text-blue-400" />
                    Информация об игре
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="rounded-lg bg-white/5 p-3 text-center">
                      <div className="text-[10px] text-slate-400 mb-1">Тиражей</div>
                      <div className="text-lg font-bold text-white">{selectedGame.draws.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg bg-white/5 p-3 text-center">
                      <div className="text-[10px] text-slate-400 mb-1">Аномалия</div>
                      <div className={`text-lg font-bold ${selectedGame.score < 25 ? 'text-emerald-400' : selectedGame.score < 50 ? 'text-amber-400' : 'text-red-400'}`}>
                        {selectedGame.score}
                      </div>
                    </div>
                    <div className="rounded-lg bg-white/5 p-3 text-center">
                      <div className="text-[10px] text-slate-400 mb-1">χ² p-value</div>
                      <div className="text-lg font-bold text-white">{selectedGame.chi2_p}</div>
                    </div>
                    <div className="rounded-lg bg-white/5 p-3 text-center">
                      <div className="text-[10px] text-slate-400 mb-1">Статус</div>
                      <Badge className={`text-[10px] border ${getVerdictBadge(selectedGame.verdict, selectedGame.verdict_color)}`}>
                        {selectedGame.verdict}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Draw Format Card */}
              <Card className="border-white/10 bg-white/5 backdrop-blur-sm mb-4">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileText className="h-4 w-4 text-amber-400" />
                    Формат данных тиража
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(() => {
                    const fmt = GAME_FORMATS[selectedGame.key || '']
                    if (!fmt) return <p className="text-xs text-slate-500">Формат неизвестен</p>
                    return (
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          <div className="rounded-lg bg-white/5 p-2.5">
                            <div className="text-[10px] text-slate-500">Блоков</div>
                            <div className="text-xs font-bold text-white">{fmt.blocks}</div>
                          </div>
                          <div className="rounded-lg bg-white/5 p-2.5">
                            <div className="text-[10px] text-slate-500">Блок 1</div>
                            <div className="text-xs font-bold text-white">{fmt.pick_b1} чисел из {fmt.b1_range}</div>
                          </div>
                          <div className="rounded-lg bg-white/5 p-2.5">
                            <div className="text-[10px] text-slate-500">Блок 2</div>
                            <div className="text-xs font-bold text-white">{fmt.pick_b2} чисел из {fmt.b2_range}</div>
                          </div>
                        </div>
                        <div className="rounded-lg bg-white/5 p-2.5">
                          <div className="text-[10px] text-slate-500 mb-1">Формат строки (date||number||block1||block2)</div>
                          <code className="block text-[11px] font-mono text-cyan-300 bg-black/30 rounded p-2 overflow-x-auto">{fmt.example}</code>
                        </div>
                        <p className="text-[10px] text-slate-500">Каждый тираж содержит дату, номер тиража и числа для предсказания в двух блоках. Модель анализирует историю тиражей для генерации прогноза.</p>
                      </div>
                    )
                  })()}
                </CardContent>
              </Card>

              {/* Fetch Draws Section */}
              <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Download className="h-4 w-4 text-emerald-400" />
                    Загрузка тиражей
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400">
                    Выгрузка всех тиражей с stoloto.ru API
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!fetchDone && !fetchLoading && !fetchError && (
                    <Button
                      onClick={handleFetchDraws}
                      className="w-full h-12 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-semibold text-sm"
                    >
                      <Download className="h-5 w-5 mr-2" />
                      Загрузить все тиражи
                    </Button>
                  )}

                  {fetchLoading && (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3">
                        <Loader2 className="h-5 w-5 text-emerald-400 animate-spin" />
                        <span className="text-sm text-slate-300">Загрузка тиражей с stoloto.ru...</span>
                      </div>
                      <Progress className="h-2 bg-white/10" />
                      <p className="text-[11px] text-slate-500">Это может занять несколько минут</p>
                    </div>
                  )}

                  {fetchError && (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-red-400">
                        <AlertTriangle className="h-5 w-5" />
                        <span className="text-sm whitespace-pre-line">{fetchError}</span>
                      </div>
                      <Button variant="outline" size="sm" onClick={handleFetchDraws} className="border-red-500/30 text-red-400">
                        <RefreshCw className="h-4 w-4 mr-1" /> Повторить
                      </Button>
                    </div>
                  )}

                  {fetchDone && fetchResult && (
                    <motion.div {...fadeIn}>
                      <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-4 flex items-center gap-3">
                        <CheckCircle2 className="h-6 w-6 text-emerald-400 shrink-0" />
                        <div>
                          <p className="text-sm font-medium text-emerald-300">
                            {fetchResult.total_draws.toLocaleString()} тиражей загружено
                          </p>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            Файл: {fetchResult.data_file}
                          </p>
                        </div>
                      </div>
                      <Button
                        onClick={() => setStep(3)}
                        className="w-full h-12 mt-4 bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-500 hover:to-indigo-400 text-white font-semibold text-sm"
                      >
                        Далее: Запустить анализ
                        <ArrowRight className="h-5 w-5 ml-2" />
                      </Button>
                    </motion.div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════════════════════ */}
          {/* STEP 3: Predictions                                           */}
          {/* ═══════════════════════════════════════════════════════════════ */}
          {step === 3 && selectedGame && (
            <motion.div key="step3" {...fadeIn}>
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
                    <Button
                      onClick={handlePredict}
                      className="h-12 px-8 bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-500 hover:to-indigo-400 text-white font-semibold"
                    >
                      <Brain className="h-5 w-5 mr-2" />
                      Запустить анализ (183 моделей)
                    </Button>
                  </CardContent>
                </Card>
              )}

              {predictLoading && (
                <Card className="border-blue-500/30 bg-blue-500/5">
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
                      <p className="text-[10px] text-slate-500 text-center">Это может занять до нескольких минут</p>
                    </div>
                  </CardContent>
                </Card>
              )}

              {predictError && (
                <Card className="border-red-500/30 bg-red-500/5">
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
                <motion.div className="space-y-4" {...fadeIn}>
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
                              {(predictResult.consensus_strength.block1 * 100).toFixed(1)}%
                            </div>
                          </div>
                          <div className="rounded-lg bg-white/5 p-3 text-center">
                            <div className="text-[10px] text-slate-400 mb-1">Согласие Б2</div>
                            <div className="text-lg font-bold text-emerald-400">
                              {(predictResult.consensus_strength.block2 * 100).toFixed(1)}%
                            </div>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Accuracy Stats */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Backtest */}
                    {predictResult.backtest && ('last_50_avg' in (predictResult.backtest as Record<string, unknown>) || 'avg_hits' in (predictResult.backtest as Record<string, unknown>)) && (
                      <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-xs flex items-center gap-2">
                            <TrendingUp className="h-3.5 w-3.5 text-amber-400" />
                            Бэктест (последние тиражи)
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          {([['50', '100', '200'] as const]).map((n) => {
                            const key = `last_${n}_avg` as const
                            const val = (predictResult.backtest as Record<string, number>)[key]
                            return (
                              <div key={n} className="flex justify-between items-center text-xs">
                                <span className="text-slate-400">Последние {n}</span>
                                <span className="font-mono text-white">{val !== undefined ? val.toFixed(2) : '—'}</span>
                              </div>
                            )
                          })}
                        </CardContent>
                      </Card>
                    )}

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
                  </div>

                  {/* Monte Carlo + Random Baseline */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {predictResult.monte_carlo && 'expected_hits' in (predictResult.monte_carlo as Record<string, unknown>) && (
                      <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-xs flex items-center gap-2">
                            <Activity className="h-3.5 w-3.5 text-cyan-400" />
                            Monte Carlo (5000 итер.)
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

                  {/* Method Breakdown */}
                  {predictResult.prediction.block1_methods && predictResult.prediction.block1_methods.length > 1 && (
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

                  {/* Actions */}
                  <div className="flex gap-3">
                    <Button
                      onClick={() => setStep(4)}
                      className="flex-1 h-12 bg-gradient-to-r from-violet-600 to-purple-500 hover:from-violet-500 hover:to-purple-400 text-white font-semibold text-sm"
                    >
                      Далее: Pipeline
                      <ArrowRight className="h-5 w-5 ml-2" />
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => { setStep(1); setSelectedGame(null); setPredictResult(null) }}
                      className="h-12 border-white/10 text-slate-400 hover:text-white hover:bg-white/5"
                    >
                      <RefreshCw className="h-4 w-4 mr-1" />
                      Заново
                    </Button>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════════════════════ */}
          {/* STEP 4: Pipeline Analysis                                     */}
          {/* ═══════════════════════════════════════════════════════════════ */}
          {step === 4 && selectedGame && (
            <motion.div key="step4" {...fadeIn}>
              <div className="flex items-center gap-3 mb-4">
                <Button variant="ghost" size="sm" onClick={() => setStep(3)} className="text-slate-400 hover:text-white">
                  <ArrowLeft className="h-4 w-4 mr-1" /> Назад
                </Button>
                <h2 className="text-lg font-bold">Pipeline усреднения</h2>
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
                        7 запусков с разными seed → взвешенное голосование → STD/RNG разделение
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
                <Card className="border-violet-500/30 bg-violet-500/5">
                  <CardContent className="py-8 flex flex-col items-center gap-4">
                    <Loader2 className="h-10 w-10 text-violet-400 animate-spin" />
                    <div className="text-center">
                      <p className="text-sm font-medium text-violet-300">Запуск 7 прогонов...</p>
                      <p className="text-xs text-slate-400 mt-1">
                        Каждый прогон с уникальным seed → взвешенное голосование
                      </p>
                    </div>
                    <div className="w-full max-w-xs">
                      <Progress className="h-2 bg-white/10" />
                    </div>
                  </CardContent>
                </Card>
              )}

              {pipelineError && (
                <Card className="border-red-500/30 bg-red-500/5">
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
                <motion.div className="space-y-4" {...fadeIn}>
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

                  {/* STD vs RNG */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-xs flex items-center gap-2">
                          <Eye className="h-3.5 w-3.5 text-cyan-400" />
                          STD-специфичный прогноз
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <div className="flex flex-wrap gap-1">
                          {pipelineResult.std_prediction.block1.map((n, i) => (
                            <span key={i} className="inline-flex items-center h-7 min-w-7 justify-center rounded-full text-[11px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/20">
                              {n}
                            </span>
                          ))}
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {pipelineResult.std_prediction.block2.map((n, i) => (
                            <span key={i} className="inline-flex items-center h-7 min-w-7 justify-center rounded-full text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/20">
                              {n}
                            </span>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-xs flex items-center gap-2">
                          <RefreshCw className="h-3.5 w-3.5 text-amber-400" />
                          RNG-специфичный прогноз
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <div className="flex flex-wrap gap-1">
                          {pipelineResult.rng_prediction.block1.map((n, i) => (
                            <span key={i} className="inline-flex items-center h-7 min-w-7 justify-center rounded-full text-[11px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/20">
                              {n}
                            </span>
                          ))}
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {pipelineResult.rng_prediction.block2.map((n, i) => (
                            <span key={i} className="inline-flex items-center h-7 min-w-7 justify-center rounded-full text-[11px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/20">
                              {n}
                            </span>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  </div>

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
          )}
        </AnimatePresence>
      </main>

      {/* ── Downloads & Setup Section ────────────────────────────────── */}
      <section className="border-t border-white/10 bg-white/[0.02]">
        <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <button
              onClick={handleDownloadProject}
              disabled={downloading}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-blue-500/15 border border-blue-500/30 text-blue-400 text-xs font-medium hover:bg-blue-500/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              {downloading ? 'Создание архива...' : 'Скачать весь проект (.tar.gz)'}
            </button>
            <button
              onClick={() => setShowSetup(!showSetup)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-white/10 text-slate-400 text-xs font-medium hover:bg-white/5 transition-colors"
            >
              <Terminal className="h-4 w-4" />
              Как запустить локально
              <ChevronRight className={`h-3.5 w-3.5 transition-transform ${showSetup ? 'rotate-90' : ''}`} />
            </button>
          </div>

          {showSetup && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="rounded-xl border border-white/10 bg-[#0d1225] overflow-hidden"
            >
              <div className="p-4 space-y-2.5">
                <p className="text-[11px] font-bold text-slate-300 flex items-center gap-2 mb-3">
                  <Terminal className="h-3.5 w-3.5 text-blue-400" />
                  Быстрая установка (локально)
                </p>

                {/* Step 1 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold mt-0.5 shrink-0">1</span>
                  <p className="text-[11px] text-slate-400">
                    Скачайте архив проекта (кнопка выше)
                  </p>
                </div>

                {/* Step 2 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold mt-0.5 shrink-0">2</span>
                  <p className="text-[11px] text-slate-400">
                    Установите <a href="https://nodejs.org/en/download" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline font-medium">Node.js</a> (LTS)
                  </p>
                </div>

                {/* Step 3 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold mt-0.5 shrink-0">3</span>
                  <p className="text-[11px] text-slate-400">
                    Установите <a href="https://www.python.org/downloads/" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline font-medium">Python 3.10+</a> с галочкой <code className="text-cyan-300 bg-black/30 px-1 rounded">Add to PATH</code>
                  </p>
                </div>

                {/* Step 4 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold mt-0.5 shrink-0">4</span>
                  <p className="text-[11px] text-slate-400">
                    Распакуйте архив и откройте терминал в папке проекта
                  </p>
                </div>

                {/* Step 5 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold mt-0.5 shrink-0">5</span>
                  <p className="text-[11px] text-slate-400">Установите зависимости:</p>
                </div>

                <div className="ml-6 flex items-center gap-1.5">
                  <code className="flex-1 text-[11px] font-mono text-cyan-300 bg-black/40 rounded-lg px-3 py-1.5">
                    npm install
                  </code>
                  <CopyButton text="npm install" />
                </div>

                {/* Step 6 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold mt-0.5 shrink-0">6</span>
                  <p className="text-[11px] text-slate-400">Python-зависимости:</p>
                </div>

                <div className="ml-6 flex items-center gap-1.5">
                  <code className="flex-1 text-[11px] font-mono text-cyan-300 bg-black/40 rounded-lg px-3 py-1.5">
                    pip install requests numpy scipy
                  </code>
                  <CopyButton text="pip install requests numpy scipy" />
                </div>

                {/* Step 7 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-blue-500/20 text-blue-400 text-[9px] font-bold mt-0.5 shrink-0">7</span>
                  <p className="text-[11px] text-slate-400">Запустите:</p>
                </div>

                <div className="ml-6 flex items-center gap-1.5">
                  <code className="flex-1 text-[11px] font-mono text-cyan-300 bg-black/40 rounded-lg px-3 py-1.5">
                    npm run dev
                  </code>
                  <CopyButton text="npm run dev" />
                </div>

                {/* Step 8 */}
                <div className="flex items-start gap-2">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[9px] font-bold mt-0.5 shrink-0">8</span>
                  <p className="text-[11px] text-slate-400">
                    Откройте <code className="text-emerald-300 bg-black/30 px-1 rounded">http://localhost:3000</code>
                  </p>
                </div>

                {/* Troubleshooting */}
                <div className="border-t border-white/10 pt-2 mt-2">
                  <p className="text-[10px] text-slate-500 flex items-center gap-1.5">
                    <AlertTriangle className="h-3 w-3 text-amber-400" />
                    Если &quot;npm/python не найден&quot; — перезапустите терминал после установки. Порт занят? → <code className="text-cyan-300">npx next dev -p 3001</code>
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          <div className="text-center">
            <span className="text-[11px] text-slate-500">
              Next.js 16 · npm · Python 3.10+ · NumPy
            </span>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/10 bg-[#0a0f1e]/80 py-3">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between text-[11px] text-slate-500">
          <span>Локальный предсказатель v22.0</span>
          <span>183 моделей · DualBayesRing · k-fold CV</span>
        </div>
      </footer>
    </div>
  )
}
