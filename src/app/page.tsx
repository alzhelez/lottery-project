'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Keyboard } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Brain, Download, Loader2, AlertTriangle,
  ChevronRight, Terminal, Shield, Sun, Moon, FlaskConical,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'sonner'
import { useTheme } from 'next-themes'

// Extracted components
import { CopyButton } from '@/components/lottery/CopyButton'
import { StepIndicator } from '@/components/lottery/StepIndicator'
import { Step1Analysis } from '@/components/lottery/Step1Analysis'
import { Step2Draws } from '@/components/lottery/Step2Draws'
import { Step3Predict } from '@/components/lottery/Step3Predict'
import { Step4Pipeline } from '@/components/lottery/Step4Pipeline'
import { ErrorBoundary } from '@/components/ErrorBoundary'

// God Mode component
import { StepGodMode } from '@/components/lottery/StepGodMode'

// Test docs
import TestDocsSection from '@/components/TestDocsSection'

// Shared types and constants
import type {
  GameAnalysis, GameCategories, PredictionResult, PipelineResult, GodModeResult, WizardStep,
} from '@/components/lottery/types'
// v39.2.2: fadeIn removed — was unused

// Shared utilities
import { safeJsonFetch } from '@/lib/fetch'
import { usePolling } from '@/hooks/usePolling'
import { adaptPredictResult, adaptPipelineResult } from '@/lib/adapters'

// ── Constants ─────────────────────────────────────────────────────────

const FETCH_TIMEOUT_ANALYZE  = 30_000
const FETCH_TIMEOUT_FETCH    = 30_000
const FETCH_TIMEOUT_PREDICT  = 30_000
const FETCH_TIMEOUT_PIPELINE = 30_000
const FETCH_TIMEOUT_GODMODE = 30_000
const REFRESH_POLL_DELAY     = 5_000

// ── Component ────────────────────────────────────────────────────────────────

export default function Home() {
  const { theme, setTheme } = useTheme()
  const [downloading, setDownloading] = useState(false)
  const [downloadingTests, setDownloadingTests] = useState(false)
  const [showSetup, setShowSetup] = useState(false)

  // ── Download project (#4: toast on error) ─────────────────────────────
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
      toast.success('Проект успешно скачан')
    } catch (err) {
      console.error('Download failed:', err)
      toast.error('Не удалось скачать проект. Попробуйте снова.')
    } finally {
      setDownloading(false)
    }
  }

  // ── Download tests ─────────────────────────────────────────────────────
  const handleDownloadTests = async () => {
    setDownloadingTests(true)
    try {
      const res = await fetch('/api/download-tests')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'lottery-tests.tar.gz'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('Автотесты успешно скачаны')
    } catch (err) {
      console.error('Download tests failed:', err)
      toast.error('Не удалось скачать автотесты. Попробуйте снова.')
    } finally {
      setDownloadingTests(false)
    }
  }

  // ── State ──────────────────────────────────────────────────────────────────

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
  const [fetchRefreshing, setFetchRefreshing] = useState(false)
  const [fetchRefreshElapsed, setFetchRefreshElapsed] = useState(0)

  const [predictLoading, setPredictLoading] = useState(false)
  const [predictResult, setPredictResult] = useState<PredictionResult | null>(null)
  const [predictError, setPredictError] = useState<string | null>(null)

  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null)
  const [pipelineError, setPipelineError] = useState<string | null>(null)

  const [enableCv, setEnableCv] = useState(false)
  const [activeModelCount, setActiveModelCount] = useState<number | null>(null)
  const [predictPollSeconds, setPredictPollSeconds] = useState(0)

  // ── God Mode state ──────────────────────────────────────────────────
  const [godModeLoading, setGodModeLoading] = useState(false)
  const [godModeResult, setGodModeResult] = useState<GodModeResult | null>(null)
  const [godModeError, setGodModeError] = useState<string | null>(null)
  const [godModeProgress, setGodModeProgress] = useState<{ completed: number; total: number } | null>(null)
  // v38.2.3: ETA tracking for God Mode progress
  const [godModeEta, setGodModeEta] = useState<{ startedAt: number; avgRunDurationMs?: number } | null>(null)
  // v39.2.2: Ref to avoid stale closure in _pollGodMode
  const godModeEtaRef = useRef(godModeEta)
  useEffect(() => { godModeEtaRef.current = godModeEta }, [godModeEta])
  const [godModeMaxRuns, setGodModeMaxRuns] = useState(50)

  // ── God Mode path ───────────────────────────────────────────────────
  const [godModePath, setGodModePath] = useState(false)

  // Polling hook (#6) — notify user on network errors
  const onErrorRef = useRef((err: Error) => toast.error('Ошибка подключения: ' + err.message))
  useEffect(() => { onErrorRef.current = (err: Error) => toast.error('Ошибка подключения: ' + err.message) }, [])

  // v38.2.6: Increased maxRetries from 60 (5 min) to 1200 (100 min).
  // God Mode with 50 runs × ~2 min each = ~100 min total. Previous limit
  // caused polling to stop after just 5 minutes, freezing the progress bar.
  // v39.2.2: Stable onError callback to avoid re-creating usePolling on every render
  const stableOnError = useCallback((err: Error) => onErrorRef.current(err), [])
  const { startPolling, versionRef } = usePolling({
    maxRetries: 1200,
    delayMs: REFRESH_POLL_DELAY,
    onError: stableOnError,
  })
  const fetchResultRef = useRef(fetchResult)
  useEffect(() => { fetchResultRef.current = fetchResult }, [fetchResult])

  // ── #12: Persist results to sessionStorage (survives page refresh) ─────────
  const PERSIST_KEY = 'lp_state'
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(PERSIST_KEY)
      if (!saved) return
      const s = JSON.parse(saved)
      if (s.step && s.step > 1) {
        const savedGame = sessionStorage.getItem('lp_selected_game')
        if (savedGame) {
          setStep(s.step)
        }
        // else: step stays at 1 (default) since selectedGame hasn't been restored yet
      } else if (s.step) {
        setStep(s.step)
      }
      if (s.enableCv) setEnableCv(s.enableCv)
      if (s.activeModelCount) setActiveModelCount(s.activeModelCount)
      if (s.fetchDone && s.fetchResult) { setFetchDone(true); setFetchResult(s.fetchResult) }
      if (s.predictResult) setPredictResult(s.predictResult)
      if (s.pipelineResult) setPipelineResult(s.pipelineResult)
      if (s.godModeResult) setGodModeResult(s.godModeResult)
      if (s.godModePath) setGodModePath(true)
    } catch { /* ignore corrupt data */ }
  }, []) // initial mount only — reads persisted state

  useEffect(() => {
    try {
      sessionStorage.setItem(PERSIST_KEY, JSON.stringify({
        step, enableCv, activeModelCount, fetchDone, fetchResult, predictResult, pipelineResult,
        godModeResult, godModePath,
      }))
    } catch { /* quota exceeded */ }
  }, [step, enableCv, activeModelCount, fetchDone, fetchResult, predictResult, pipelineResult, godModeResult, godModePath])

  // ── Step 1: Auto-analyze on mount ──────────────────────────────────────────

  const runAnalyze = useCallback(async (isPoll = false) => {
    if (!isPoll) {
      setAnalyzeLoading(true)
      setAnalyzeError(null)
    }
    try {
      const { data, ok } = await safeJsonFetch('/api/lottery/analyze', { method: 'POST' }, FETCH_TIMEOUT_ANALYZE)
      if (!ok || data.error) {
        const msg = data.retry_after
          ? `${data.error} (повторите через ${data.retry_after}с)`
          : data.hint
            ? `${data.error}\n${data.hint}`
            : (data.error || 'Ошибка анализа')
        throw new Error(msg)
      }
      const gamesData = data.games || []
      setGames(gamesData)
      setCategories(data.categories || null)
      // v39.3.0: Show toast on manual refresh only (not on auto-poll)
      if (!isPoll && gamesData.length > 0) {
        toast.success(`Анализ обновлён: ${gamesData.length} игр`)
      }
      if (typeof window !== 'undefined') {
        const saved = sessionStorage.getItem('lp_selected_game')
        if (saved && data.games) {
          const found = data.games.find((g: GameAnalysis) => g.key === saved || g.name === saved)
          if (found) setSelectedGame(found)
        }
      }
      if (data._refreshing) {
        const v = versionRef.current
        setTimeout(() => {
          if (versionRef.current !== v) return
          runAnalyze(true)
        }, REFRESH_POLL_DELAY)
      }
    } catch (err) {
      if (!isPoll) setAnalyzeError(err instanceof Error ? err.message : 'Ошибка анализа')
    } finally {
      if (!isPoll) setAnalyzeLoading(false)
    }
  }, [versionRef])

  useEffect(() => {
    runAnalyze()
  }, [runAnalyze])

  // ── Step 2: Fetch draws ────────────────────────────────────────────────────

  const handleFetchDraws = async () => {
    if (!selectedGame?.key) return
    if (fetchLoading) return
    setFetchLoading(true)
    setFetchError(null)
    setFetchDone(false)
    try {
      const { data, ok } = await safeJsonFetch('/api/lottery/fetch-draws', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key }),
      }, FETCH_TIMEOUT_FETCH)
      if (!ok || data.error) {
        const msg = data.retry_after
          ? `${data.error || 'Ошибка'} (повторите через ${data.retry_after}с)`
          : data.hint
            ? `${data.error || 'Ошибка'}\n${data.hint}`
            : (data.error || 'Ошибка загрузки')
        throw new Error(msg)
      }
      const totalDraws = typeof data.total_draws === 'number' ? data.total_draws : 0
      setFetchResult({ game: data.game || '', total_draws: totalDraws, data_file: data.data_file || '' })
      if (totalDraws > 0) {
        setFetchDone(true)
        setFetchLoading(false)
        if (data._refreshing) {
          setFetchRefreshing(true)
          _pollFetchDraws(selectedGame.key)
        }
      } else if (data._refreshing) {
        // No file exists yet — keep normal loading spinner (not "background mode")
        setFetchDone(false)
        // fetchLoading stays true — spinner keeps showing until polling finds draws
        _pollFetchDraws(selectedGame.key, true)  // true = first-time load
      } else {
        setFetchLoading(false)
        setFetchError('Не удалось загрузить тиражи для этой игры. Попробуйте другую игру.')
      }
    } catch (err) {
      setFetchLoading(false)
      setFetchError(err instanceof Error ? err.message : 'Ошибка загрузки тиражей')
    }
  }

  // #6: Use polling hook for fetch-draws
  const _pollFetchDraws = useCallback((gameKey: string, firstTimeLoad = false) => {
    startPolling(async () => {
      const { data, ok } = await safeJsonFetch('/api/lottery/fetch-draws', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: gameKey }),
      }, FETCH_TIMEOUT_FETCH)
      if (!ok || data.error) return true // continue polling (might be pending)
      const totalDraws = typeof data.total_draws === 'number' ? data.total_draws : 0
      if (data._refresh_max && data._refresh_elapsed > data._refresh_max) {
        setFetchLoading(false)
        setFetchRefreshing(false)
        setFetchRefreshElapsed(0)
        if (totalDraws === 0) {
          setFetchError('Не удалось загрузить тиражи. Попробуйте ещё раз.')
        }
        return false // stop polling
      }
      setFetchRefreshElapsed(data._refresh_elapsed || 0)
      if (totalDraws > 0) {
        setFetchResult({ game: data.game || '', total_draws: totalDraws, data_file: data.data_file || '' })
        setFetchDone(true)
        setFetchLoading(false)
        if (!data._refreshing) {
          setFetchRefreshing(false)
          setFetchRefreshElapsed(0)
          return false // stop polling
        }
        // Data arrived — if was first-time load, stop background refresh indicator
        if (firstTimeLoad) {
          setFetchRefreshing(false)
          setFetchRefreshElapsed(0)
          return false // stop polling — user has their data
        }
      }
      return !!data._refreshing // continue if still refreshing
    })
  }, [startPolling])

  // ── Step 3: Run predictions ────────────────────────────────────────────────

  const handlePredict = async () => {
    if (!selectedGame) return
    if (predictLoading) return
    setPredictLoading(true)
    setPredictError(null)
    setPredictResult(null)
    let delegatedToPolling = false
    try {
      const dataFile = fetchResult?.data_file || ''
      const { data: raw, ok } = await safeJsonFetch('/api/lottery/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key, data_file: dataFile, enable_cv: enableCv }),
      }, FETCH_TIMEOUT_PREDICT)

      if (ok && raw._refreshing && raw.status === 'pending') {
        delegatedToPolling = true
        _pollPredict(selectedGame.key, dataFile, enableCv)
        return
      }

      if (!ok || raw.status === 'error' || raw.error) {
        const msg = raw.retry_after
          ? `${raw.error || 'Ошибка'} (повторите через ${raw.retry_after}с)`
          : raw.hint
            ? `${raw.error || 'Ошибка предсказания'}\n${raw.hint}`
            : (raw.error || 'Ошибка предсказания')
        throw new Error(msg)
      }

      const data = adaptPredictResult(raw)
      setPredictResult(data)
      const realModels = (raw.game_format as Record<string, unknown>)?.total_models
      if (typeof realModels === 'number') setActiveModelCount(realModels)

      if (raw._refreshing) {
        _pollPredict(selectedGame.key, dataFile, enableCv)
      }
    } catch (err) {
      setPredictError(err instanceof Error ? err.message : 'Ошибка предсказания')
    } finally {
      if (!delegatedToPolling) setPredictLoading(false)
    }
  }

  // #6: Use polling hook for predict
  const _pollPredict = useCallback((gameKey: string, dataFile: string, enableCvParam: boolean) => {
    startPolling(async () => {
      const { data: raw, ok } = await safeJsonFetch('/api/lottery/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: gameKey, data_file: dataFile, enable_cv: enableCvParam }),
      }, FETCH_TIMEOUT_PREDICT)
      if (!ok || raw.status === 'error' || raw.error) {
        if (raw._refreshing || raw.status === 'pending') return true // keep polling
        setPredictLoading(false)
        setPredictError(raw.error || 'Ошибка прогноза')
        return false // stop
      }
      const data = adaptPredictResult(raw)
      setPredictResult(data)
      setPredictLoading(false)
      const realModels = (raw.game_format as Record<string, unknown>)?.total_models
      if (typeof realModels === 'number') setActiveModelCount(realModels)
      return !!raw._refreshing
    })
  }, [startPolling])



  // ── Step 4: Pipeline ──────────────────────────────────────────────────────

  const handlePipeline = async () => {
    if (!selectedGame) return
    if (pipelineLoading) return
    setPipelineLoading(true)
    setPipelineError(null)
    setPipelineResult(null)
    let delegatedToPolling = false
    try {
      const dataFile = fetchResult?.data_file || ''
      const { data: raw, ok } = await safeJsonFetch('/api/lottery/pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key, data_file: dataFile }),
      }, FETCH_TIMEOUT_PIPELINE)

      if (ok && raw._refreshing && raw.status === 'pending') {
        delegatedToPolling = true
        _pollPipeline(selectedGame.key, dataFile)
        return
      }

      if (!ok || raw.status === 'error' || raw.error) {
        const msg = raw.retry_after
          ? `${raw.error || 'Ошибка'} (повторите через ${raw.retry_after}с)`
          : raw.hint
            ? `${raw.error || 'Ошибка pipeline'}\n${raw.hint}`
            : (raw.error || 'Ошибка pipeline')
        throw new Error(msg)
      }

      const data = adaptPipelineResult(raw, selectedGame.key || '')
      setPipelineResult(data)

      if (raw._refreshing) {
        _pollPipeline(selectedGame.key, dataFile)
      }
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : 'Ошибка pipeline')
    } finally {
      if (!delegatedToPolling) setPipelineLoading(false)
    }
  }

  // #6: Use polling hook for pipeline
  const _pollPipeline = useCallback((gameKey: string, dataFile: string) => {
    startPolling(async () => {
      const { data: raw, ok } = await safeJsonFetch('/api/lottery/pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json'},
        body: JSON.stringify({ game: gameKey, data_file: dataFile }),
      }, FETCH_TIMEOUT_PIPELINE)
      if (!ok || raw.status === 'error' || raw.error) {
        if (raw._refreshing || raw.status === 'pending') return true // keep polling
        setPipelineLoading(false)
        setPipelineError(raw.error || 'Ошибка Pipeline')
        return false // stop
      }
      const data = adaptPipelineResult(raw, gameKey)
      setPipelineResult(data)
      setPipelineLoading(false)
      return !!raw._refreshing
    })
  }, [startPolling])



  // ── Game selection handler ─────────────────────────────────────────────────

  const handleSelectGame = useCallback((game: GameAnalysis) => {
    versionRef.current++
    const resetStep2And3 = () => {
      setFetchDone(false)
      setFetchResult(null)
      setFetchError(null)
      setFetchLoading(false)
      setFetchRefreshing(false)
      setFetchRefreshElapsed(0)
      setPredictResult(null)
      setPredictError(null)
      setPipelineResult(null)
      setPipelineError(null)
      setGodModeResult(null)
      setGodModeError(null)
      setGodModeLoading(false)
      setGodModeProgress(null)
      setGodModeEta(null)
      setPredictLoading(false)
      setPipelineLoading(false)
    }
    if (game.redirect_target && games.length > 0) {
      const target = games.find((g: GameAnalysis) => (g.key || g.name) === game.redirect_target)
      if (target) {
        setSelectedGame(target)
        setStep(2)
        resetStep2And3()
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('lp_selected_game', target.key || target.name)
        }
        return
      }
    }
    setSelectedGame(game)
    setStep(2)
    resetStep2And3()
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('lp_selected_game', game.key || game.name)
    }
  }, [games])

  // ── #10: Predict polling elapsed timer ──────────────────────────────────
  useEffect(() => {
    if (!predictLoading) { setPredictPollSeconds(0); return }
    const timer = setInterval(() => setPredictPollSeconds(s => s + 1), 1000)
    return () => clearInterval(timer)
  }, [predictLoading])

  // ── Step 5: God Mode ──────────────────────────────────────────────

  const handleStartGodMode = async () => {
    if (!selectedGame) return
    if (godModeLoading) return
    setGodModeLoading(true)
    setGodModeError(null)
    setGodModeResult(null)
    setGodModeProgress(null)
    setGodModeEta(null)
    let delegatedToPolling = false
    try {
      const dataFile = fetchResult?.data_file || ''
      const { data, ok } = await safeJsonFetch('/api/lottery/god-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key, data_file: dataFile, max_runs: godModeMaxRuns }),
      }, FETCH_TIMEOUT_GODMODE)
      if (ok && data._refreshing && (data.status === 'pending' || data.status === 'running')) {
        delegatedToPolling = true
        if (data.runs_completed != null && data.runs_total != null) {
          setGodModeProgress({ completed: data.runs_completed, total: data.runs_total })
        }
        // v38.2.3: Capture ETA data from initial response
        if (data.started_at) {
          setGodModeEta({ startedAt: data.started_at, avgRunDurationMs: data.avg_run_duration_ms })
        }
        _pollGodMode(selectedGame.key, dataFile)
        return
      }
      if (!ok || data.error) {
        throw new Error(data.error || 'Ошибка Режима Бога')
      }
      if (data.status === 'ok') {
        setGodModeResult(data as GodModeResult)
        setGodModeLoading(false)
      }
    } catch (err) {
      setGodModeError(err instanceof Error ? err.message : 'Ошибка Режима Бога')
    } finally {
      if (!delegatedToPolling) setGodModeLoading(false)
    }
  }

  const _pollGodMode = useCallback((gameKey: string, dataFile: string) => {
    startPolling(async () => {
      const { data, ok } = await safeJsonFetch('/api/lottery/god-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game: gameKey,
          data_file: dataFile,
          max_runs: godModeMaxRuns,
          started_at: godModeEtaRef.current?.startedAt,
        }),
      }, FETCH_TIMEOUT_GODMODE)
      if (!ok || data.error) {
        // v38.3.0: Bug #9 — detect server crash
        if (data._server_crash) {
          setGodModeLoading(false)
          setGodModeError(data.error || 'Сервер перезапустился')
          return false
        }
        if (data._refreshing || data.status === 'running' || data.status === 'pending') {
          if (data.runs_completed != null) setGodModeProgress({ completed: data.runs_completed, total: data.runs_total ?? godModeMaxRuns })
          // v38.2.3: Update ETA data on every poll
          if (data.started_at) {
            setGodModeEta({ startedAt: data.started_at, avgRunDurationMs: data.avg_run_duration_ms })
          }
          return true
        }
            // v39.2.0: Only stop on explicit final error (no _refreshing).
        // God Mode runs server-side in the background — even if a poll request fails
        // (network error, timeout, server compilation via Turbopack HMR), the server
        // continues processing. Stopping polling would lose progress.
        if (data.status === 'error' && !data._refreshing) {
          setGodModeLoading(false)
          setGodModeError(data.error || 'Ошибка Режима Бога')
          return false
        }
        // Everything else is transient — keep polling
        return true
      }
      if (data.status === 'running' || data.status === 'pending') {
        if (data.runs_completed != null) setGodModeProgress({ completed: data.runs_completed, total: data.runs_total ?? godModeMaxRuns })
        // v38.2.3: Update ETA data on every poll
        if (data.started_at) {
          setGodModeEta({ startedAt: data.started_at, avgRunDurationMs: data.avg_run_duration_ms })
        }
        return true
      }
      if (data.status === 'ok') {
        setGodModeResult(data as GodModeResult)
        setGodModeLoading(false)
        setGodModeProgress(null)
        setGodModeEta(null)
        return false
      }
      return false
    })
  }, [startPolling, godModeMaxRuns])

  const handleStopGodMode = async () => {
    if (!selectedGame) return
    versionRef.current++ // stop polling
    setGodModeLoading(false)
    try {
      const dataFile = fetchResult?.data_file || ''
      await safeJsonFetch('/api/lottery/god-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game: selectedGame.key, data_file: dataFile, stop: true }),
      }, 5_000)
    } catch { /* ignore */ }
  }

  // v39.2.0: REMOVED versionRef increment on unmount.
  // Previously, incrementing versionRef on unmount stopped ALL polling when
  // the component remounted (e.g., during Turbopack HMR). This caused God Mode
  // progress to freeze at N/50 runs because the server continued processing
  // but the client stopped polling. Polling is now resilient to HMR — the
  // usePolling hook continues polling on network errors instead of stopping.

  // ── #14: Keyboard navigation ──────────────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'ArrowRight' && step < 5) {
        e.preventDefault()
        if (godModePath) {
          // God mode path: 1 → 2 → 5 only
          if (step === 1 && selectedGame) setStep(2)
          else if (step === 2 && fetchDone) { setGodModePath(true); setStep(5) }
        } else {
          // Normal path: 1 → 2 → 3 → 4
          if (step === 1 && selectedGame) setStep(2)
          else if (step === 2 && fetchDone) setStep(3)
          else if (step === 3 && predictResult) setStep(4)
        }
      }
      if (e.key === 'ArrowLeft' && step > 1) {
        e.preventDefault()
        if (godModePath && step === 5) {
          setGodModePath(false)
          setStep(2)
        } else {
          setStep((step - 1) as WizardStep)
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [step, selectedGame, fetchDone, predictResult, godModePath])

  // ── Render helpers ─────────────────────────────────────────────────────────

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

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <ErrorBoundary>
    <div className="min-h-screen flex flex-col text-white">

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-[#0a0f1e]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shrink-0">
            <Brain className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-bold text-white truncate">Локальный предсказатель</h1>
            <p className="text-[11px] text-slate-400">{activeModelCount != null ? `${activeModelCount} активных` : '107 активных'} из 133 моделей · DualBayesRing{enableCv ? ' · k-fold CV' : ''}</p>
          </div>
          <div className="ml-auto flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="relative inline-flex items-center justify-center h-7 w-7 rounded-md border border-white/10 text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label={theme === 'dark' ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'}
              suppressHydrationWarning
            >
              <Sun className="h-3.5 w-3.5 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-3.5 w-3.5 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
            </button>
            <Badge variant="outline" className="border-blue-500/30 text-blue-400 text-xs">
              v39.5.1
            </Badge>
          </div>
        </div>
      </header>

      {/* ── Step Indicator ──────────────────────────────────────────────────── */}
      <StepIndicator
        step={step}
        setStep={setStep}
        selectedGame={selectedGame}
        fetchDone={fetchDone}
        predictResult={predictResult}
        godModePath={godModePath}
        setGodModePath={setGodModePath}
      />

      {/* ── Main Content ────────────────────────────────────────────────── */}
      <main id="main-content" className="flex-1 max-w-7xl mx-auto w-full px-4 py-4">
        <AnimatePresence mode="wait">
          {step === 1 && (
            <Step1Analysis
              analyzeLoading={analyzeLoading}
              analyzeError={analyzeError}
              games={games}
              categories={categories}
              selectedGame={selectedGame}
              runAnalyze={runAnalyze}
              handleSelectGame={handleSelectGame}
            />
          )}

          {step === 2 && selectedGame && (
            <Step2Draws
              selectedGame={selectedGame}
              fetchLoading={fetchLoading}
              fetchDone={fetchDone}
              fetchResult={fetchResult}
              fetchError={fetchError}
              fetchRefreshing={fetchRefreshing}
              fetchRefreshElapsed={fetchRefreshElapsed}
              handleFetchDraws={handleFetchDraws}
              setStep={setStep}
              getVerdictBadge={getVerdictBadge}
              godModePath={godModePath}
              setGodModePath={setGodModePath}
            />
          )}

          {step === 3 && selectedGame && (
            <Step3Predict
              selectedGame={selectedGame}
              predictLoading={predictLoading}
              predictResult={predictResult}
              predictError={predictError}
              enableCv={enableCv}
              setEnableCv={setEnableCv}
              activeModelCount={activeModelCount}
              predictPollSeconds={predictPollSeconds}
              handlePredict={handlePredict}
              setStep={setStep}
            />
          )}

          {step === 4 && selectedGame && (
            <Step4Pipeline
              selectedGame={selectedGame}
              pipelineLoading={pipelineLoading}
              pipelineResult={pipelineResult}
              pipelineError={pipelineError}
              predictResult={predictResult}
              handlePipeline={handlePipeline}
              setStep={setStep}
            />
          )}

          {(step === 5 && selectedGame) && (
            <StepGodMode
              selectedGame={selectedGame}
              godModeLoading={godModeLoading}
              godModeResult={godModeResult}
              godModeError={godModeError}
              godModeProgress={godModeProgress}
              godModeEta={godModeEta}
              maxRuns={godModeMaxRuns}
              setMaxRuns={setGodModeMaxRuns}
              handleStartGodMode={handleStartGodMode}
              handleStopGodMode={handleStopGodMode}
              setStep={setStep}
              setGodModePath={setGodModePath}
            />
          )}
        </AnimatePresence>
      </main>

      
      {/* ── Version Info (downloaded build) ──────────────────────────── */}
      <section className="border-t border-white/10 bg-white/[0.02]">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-center gap-4 text-center">
            <span className="text-[11px] text-slate-500">Next.js 16 · Bun · Python 3.10+ · NumPy · 133 ML-модели</span>
            <kbd className="inline-flex items-center gap-1 text-[10px] px-2 py-1 bg-white/5 border border-white/10 rounded text-slate-400">
              <Keyboard className="h-3 w-3" /> ← → навигация
            </kbd>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/10 bg-[#0a0f1e]/80 py-3">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between text-[11px] text-slate-500">
          <span>Локальный предсказатель v39.5.1</span>
          <span>{activeModelCount != null ? activeModelCount : '107'} активных из 133 моделей · DualBayesRing{enableCv ? ' · k-fold CV' : ''}</span>
        </div>
      </footer>
    </div>
    </ErrorBoundary>
  )
}

