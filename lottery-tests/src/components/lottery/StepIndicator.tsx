'use client'

import { CheckCircle2, Shield } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import type { WizardStep, GameAnalysis, PredictionResult } from './types'

interface StepIndicatorProps {
  step: WizardStep
  setStep: (step: WizardStep) => void
  selectedGame: GameAnalysis | null
  fetchDone: boolean
  predictResult: PredictionResult | null
  godModePath: boolean
  setGodModePath: (v: boolean) => void
}

// v39.3.0: Brief descriptions for each step, shown as tooltips on hover
const STEP_TOOLTIPS: Record<number, string> = {
  1: 'Анализ 38 игр Столото: χ²-тест, аномальность, горячие/холодные числа',
  2: 'Загрузка всех тиражей с API stoloto.ru (бинарный поиск + пагинация)',
  3: 'Прогноз от 133 ML-моделей из 8 групп (частотные, импульсные, Monte Carlo и др.)',
  4: 'Pipeline: позиционный анализ + частотный анализ → взвешенное голосование → финальный прогноз',
  5: '50 последовательных прогонов с консенсусом, ранговым голосованием и meta-consensus',
}

export function StepIndicator({ step, setStep, selectedGame, fetchDone, predictResult, godModePath, setGodModePath }: StepIndicatorProps) {
  const steps = godModePath
    ? [
        { n: 1 as const, label: 'Анализ', icon: '1' },
        { n: 2 as const, label: 'Тиражи', icon: '2' },
        { n: 5 as const, label: 'Режим Бога', icon: <Shield className="h-3 w-3" />, isGodMode: true },
      ]
    : [
        { n: 1 as const, label: 'Анализ', icon: '1' },
        { n: 2 as const, label: 'Тиражи', icon: '2' },
        { n: 3 as const, label: 'Прогноз', icon: '3' },
        { n: 4 as const, label: 'Pipeline', icon: '4' },
      ]

  const maxStep = godModePath ? 5 : 4

  return (
    <nav className="max-w-7xl mx-auto w-full px-4 pt-4">
      <div className="flex items-center gap-1.5 mb-1">
        {godModePath && (
          <button
            type="button"
            onClick={() => { setGodModePath(false); setStep(2) }}
            className="text-[10px] text-violet-400/70 hover:text-violet-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded px-1"
          >
            ← Обычный режим
          </button>
        )}
      </div>
      <TooltipProvider delayDuration={300}>
      <div role="tablist" aria-label="Шаги мастера" className="flex items-center gap-1 sm:gap-2 overflow-x-auto pb-2">
        {steps.map(({ n, label, icon, isGodMode }, i) => {
          const isActive = step === n
          const isDone = step > n
          return (
            <div key={`${godModePath}-${n}`} className="flex items-center shrink-0">
              {i > 0 && (
                <div className={`w-4 sm:w-8 h-px ${isDone ? (isGodMode ? 'bg-purple-500' : 'bg-blue-500') : 'bg-white/10'}`} />
              )}
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    id={`tab-${n}`}
                    role="tab"
                    aria-selected={isActive}
                    aria-controls={`step-${n}`}
                    tabIndex={isActive ? 0 : -1}
                    onClick={() => {
                      if (n === 1) { setStep(1) }
                      else if (n === 2 && selectedGame) { setStep(2) }
                      else if (n === 3 && fetchDone) { setStep(3) }
                      else if (n === 4 && predictResult) { setStep(4) }
                      else if (n === 5 && fetchDone) { setGodModePath(true); setStep(5) }
                    }}
                    disabled={
                      (n === 2 && !selectedGame) ||
                      (n === 3 && !fetchDone) ||
                      (n === 4 && !predictResult) ||
                      (n === 5 && !fetchDone)
                    }
                    className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-3 rounded-lg text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                      isGodMode && isActive
                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                        : isGodMode && isDone
                          ? 'text-purple-400/70 hover:text-purple-300 cursor-pointer'
                          : isGodMode
                            ? 'text-slate-500 cursor-not-allowed'
                            : isActive
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                              : isDone
                                ? 'text-blue-400/70 hover:text-blue-300 cursor-pointer'
                                : 'text-slate-500 cursor-not-allowed'
                    }`}
                  >
                    <div className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      isGodMode && isActive
                        ? 'bg-purple-500 text-white'
                        : isGodMode && isDone
                          ? 'bg-purple-500/30 text-purple-400'
                          : isGodMode
                            ? 'bg-white/10 text-slate-500'
                            : isActive
                              ? 'bg-blue-500 text-white'
                              : isDone
                                ? 'bg-blue-500/30 text-blue-400'
                                : 'bg-white/10 text-slate-500'
                    }`}>
                      {isDone ? <CheckCircle2 className="h-3 w-3" /> : icon}
                    </div>
                    <span className="hidden sm:inline">{label}</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px] text-center">
                  <p>{STEP_TOOLTIPS[n]}</p>
                </TooltipContent>
              </Tooltip>
            </div>
          )
        })}
      </div>
      </TooltipProvider>
    </nav>
  )
}
