'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { Crown, Loader2, AlertTriangle, X, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import { safeJsonFetch } from '@/lib/fetch'
import { fadeIn } from './types'

interface GodModeCardProps {
  gameId: string
  dataFile: string
  maxRuns: number
  onResult: (result: Record<string, unknown>) => void
  onError: (error: string) => void
  onCancel: () => void
}

export function GodModeCard({ gameId, dataFile, maxRuns, onResult, onError, onCancel }: GodModeCardProps) {
  const [status, setStatus] = useState<'starting' | 'running' | 'done'>('starting')
  const [completedRuns, setCompletedRuns] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [currentRunInfo, setCurrentRunInfo] = useState<string>('')

  const jobIdRef = useRef<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval>>()
  const pollRef = useRef<ReturnType<typeof setInterval>>()
  const startTsRef = useRef<number>(0)
  const cancelledRef = useRef(false)

  // Use refs for callbacks to avoid stale closures in polling
  const onResultRef = useRef(onResult)
  const onErrorRef = useRef(onError)
  useEffect(() => { onResultRef.current = onResult }, [onResult])
  useEffect(() => { onErrorRef.current = onError }, [onError])

  const cleanup = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (pollRef.current) clearInterval(pollRef.current)
    timerRef.current = undefined
    pollRef.current = undefined
    setElapsed(startTsRef.current > 0 ? Math.round((Date.now() - startTsRef.current) / 1000) : 0)
  }, [])

  // Main effect: start god mode on mount
  useEffect(() => {
    let mounted = true
    cancelledRef.current = false

    const doPoll = async () => {
      if (!jobIdRef.current || cancelledRef.current) return

      try {
        const { data, ok } = await safeJsonFetch<{
          status: string
          completed_runs: number
          total_runs: number
          result?: Record<string, unknown>
          error?: string
        }>(`/api/lottery/god-mode?job_id=${jobIdRef.current}`, {}, 30_000)

        if (!mounted || cancelledRef.current) return

        if (!ok) {
          setError(data.error as string || 'Ошибка запроса')
          setStatus('done')
          cleanup()
          return
        }

        if (data.status === 'ok' && data.result) {
          setCompletedRuns(data.total_runs)
          onResultRef.current(data.result)
          setStatus('done')
          cleanup()
          return
        }

        if (data.status === 'error') {
          setError(data.error || 'Ошибка анализа')
          onErrorRef.current(data.error || 'Ошибка анализа')
          setStatus('done')
          cleanup()
          return
        }

        // Still running
        if (typeof data.completed_runs === 'number') {
          setCompletedRuns(data.completed_runs)
          setCurrentRunInfo(`Прогон ${data.completed_runs + 1} из ${data.total_runs}`)
        }
      } catch {
        // Network error, continue polling
      }
    }

    const doStart = async () => {
      try {
        const { data, ok } = await safeJsonFetch<{
          status: string
          job_id: string
          total_runs: number
          error?: string
        }>('/api/lottery/god-mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            game: gameId,
            data_file: dataFile,
            max_runs: maxRuns,
          }),
        }, 30_000)

        if (!mounted || cancelledRef.current) return

        if (!ok || data.error) {
          setError((data.error as string) || 'Не удалось запустить анализ')
          setStatus('done')
          return
        }

        jobIdRef.current = data.job_id
        setStatus('running')
        startTsRef.current = Date.now()

        // Start elapsed timer
        timerRef.current = setInterval(() => {
          if (startTsRef.current > 0) {
            setElapsed(Math.round((Date.now() - startTsRef.current) / 1000))
          }
        }, 1000)

        // Start polling every 5 seconds
        pollRef.current = setInterval(doPoll, 5000)

        // Also poll immediately
        setTimeout(doPoll, 2000)
      } catch {
        if (!mounted || cancelledRef.current) return
        setError('Ошибка подключения')
        setStatus('done')
      }
    }

    doStart()

    return () => {
      mounted = false
      cancelledRef.current = true
      cleanup()
    }
  }, [gameId, dataFile, maxRuns, cleanup])

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    if (m > 0) return `${m}м ${sec}с`
    return `${sec}с`
  }

  const progress = maxRuns > 0 ? (completedRuns / maxRuns) * 100 : 0

  return (
    <motion.div {...fadeIn}>
      <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent overflow-hidden relative">
        <div className="absolute top-0 right-0 w-40 h-40 bg-amber-500/5 rounded-full blur-3xl" />

        {status === 'running' && (
          <div className="absolute top-3 right-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                cancelledRef.current = true
                cleanup()
                onCancel()
              }}
              className="text-slate-400 hover:text-white h-7 w-7 p-0"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        <CardContent className="py-8 flex flex-col items-center gap-5 relative">
          {/* Icon */}
          <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/20">
            {status === 'running' ? (
              <Crown className="h-8 w-8 text-white animate-pulse" />
            ) : error ? (
              <AlertTriangle className="h-8 w-8 text-white" />
            ) : (
              <Sparkles className="h-8 w-8 text-white" />
            )}
          </div>

          {/* Title */}
          <div className="text-center">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Crown className="h-4 w-4 text-amber-400" />
              Режим Бога
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Многократный анализ с различными параметрами
            </p>
          </div>

          {/* Progress */}
          {status === 'running' && (
            <div className="w-full max-w-sm space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-amber-300 font-medium">
                  {currentRunInfo || `Прогон 1 из ${maxRuns}`}
                </span>
                <span className="text-slate-400">
                  {completedRuns}/{maxRuns}
                </span>
              </div>
              <Progress value={progress} className="h-2.5 bg-white/10" />
              <div className="flex items-center justify-between text-[10px] text-slate-500">
                <span className="flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin text-amber-400" />
                  Прошло {formatTime(elapsed)}
                </span>
                <span>{progress.toFixed(0)}% завершено</span>
              </div>

              {/* Run milestones */}
              <div className="flex gap-1 mt-1">
                {Array.from({ length: maxRuns }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-full transition-colors ${
                      i < completedRuns
                        ? 'bg-amber-400'
                        : i === completedRuns
                          ? 'bg-amber-400/50 animate-pulse'
                          : 'bg-white/10'
                    }`}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="text-center space-y-3">
              <p className="text-sm text-red-400 whitespace-pre-line max-w-sm">{error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={onCancel}
                className="border-white/10 text-slate-400"
              >
                Закрыть
              </Button>
            </div>
          )}

          {/* Info badges */}
          <div className="flex items-center gap-2 flex-wrap justify-center">
            <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400">
              {maxRuns} прогонов
            </Badge>
            <Badge variant="outline" className="text-[10px] border-white/10 text-slate-400">
              Predict + Step Analysis + Pipeline
            </Badge>
            <Badge variant="outline" className="text-[10px] border-white/10 text-slate-400">
              Вариативные параметры
            </Badge>
          </div>

          {status === 'running' && (
            <p className="text-[10px] text-slate-500 text-center max-w-sm">
              Каждый прогон использует уникальную комбинацию параметров:
              диапазон тиражей, количество шагов анализа, весовые коэффициенты.
              Результаты агрегируются для получения наиболее вероятных комбинаций.
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
