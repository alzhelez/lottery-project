'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ArrowLeft, ArrowRight, Download, CheckCircle2, AlertTriangle, RefreshCw, Loader2, ExternalLink, Layers, FileText, Dice1, Shield } from 'lucide-react'
import { motion } from 'framer-motion'
import type { GameAnalysis, WizardStep } from './types'
import { GAME_ICONS, GAME_FORMATS, fadeIn } from './types'

interface Step2DrawsProps {
  selectedGame: GameAnalysis
  fetchLoading: boolean
  fetchDone: boolean
  fetchResult: { game: string; total_draws: number; data_file: string } | null
  fetchError: string | null
  fetchRefreshing: boolean
  fetchRefreshElapsed: number
  handleFetchDraws: () => void
  setStep: (step: WizardStep) => void
  getVerdictBadge: (verdict: string, color: string) => string
  godModePath: boolean
  setGodModePath: (v: boolean) => void
}

export function Step2Draws({
  selectedGame,
  fetchLoading,
  fetchDone,
  fetchResult,
  fetchError,
  fetchRefreshing,
  fetchRefreshElapsed,
  handleFetchDraws,
  setStep,
  getVerdictBadge,
  godModePath,
  setGodModePath,
}: Step2DrawsProps) {
  return (
    <motion.div key="step2" id="step-2" role="tabpanel" aria-labelledby="tab-2" {...fadeIn}>
      <div className="flex items-center gap-3 mb-4">
        <Button variant="ghost" size="sm" onClick={() => { setGodModePath(false); setStep(1) }} className="text-slate-400 hover:text-white">
          <ArrowLeft className="h-4 w-4 mr-1" /> Назад
        </Button>
        <div className="flex items-center gap-2">
          {(() => { const I = GAME_ICONS[selectedGame.key || ''] || Dice1; return <I className="h-5 w-5 text-blue-400" /> })()}
          <h2 className="text-lg font-bold">{selectedGame.name}</h2>
          {selectedGame.redirect_target && (
            <span className="text-xs text-slate-500">(→ {selectedGame.redirect_target})</span>
          )}
          {selectedGame.key && (
            <a
              href={`https://www.stoloto.ru/${selectedGame.key}/archive`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors px-2 py-1 rounded-md bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <ExternalLink className="h-3 w-3" />
              <span className="hidden sm:inline">stoloto.ru</span>
            </a>
          )}
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
              <div className="text-lg font-bold text-white">{selectedGame.chi2_p != null ? selectedGame.chi2_p : '—'}</div>
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
            <div role="status" aria-live="polite" className="space-y-3">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 text-emerald-400 animate-spin" />
                <span className="text-sm text-slate-300">Загрузка тиражей с stoloto.ru...</span>
              </div>
              <Progress className="h-2 bg-white/10" />
              <p className="text-[11px] text-slate-500">Это может занять несколько минут</p>
            </div>
          )}

          {fetchError && (
            <div role="status" aria-live="polite" className="space-y-3">
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
                  {!fetchRefreshing && (
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Данные актуальны
                    </p>
                  )}
                </div>
              </div>
              {!fetchRefreshing && fetchDone && (
                <div className="flex items-center gap-2 mt-2">
                  <p className="text-[11px] text-emerald-400">
                    ✅ Все данные актуальны
                  </p>
                  <Button variant="outline" size="sm" onClick={handleFetchDraws}
                    className="border-emerald-500/30 text-emerald-400 text-xs h-7 ml-auto">
                    <RefreshCw className="h-3 w-3 mr-1" /> Обновить тиражи
                  </Button>
                </div>
              )}
              {fetchRefreshing && fetchDone && (
                <div className="flex items-center gap-2 mt-2">
                  <Button variant="outline" size="sm" onClick={handleFetchDraws}
                    className="border-emerald-500/30 text-emerald-400 text-xs h-7">
                    <RefreshCw className="h-3 w-3 mr-1" /> Обновить тиражи
                  </Button>
                  <span className="text-[10px] text-amber-400 animate-pulse">
                    🔄 Обновление... ({Math.round(fetchRefreshElapsed / 1000)}с)
                  </span>
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-3 mt-4">
                <Button
                  onClick={() => { setGodModePath(false); setStep(3) }}
                  className="flex-1 h-12 bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-500 hover:to-indigo-400 text-white font-semibold text-sm"
                >
                  Далее: Прогноз
                  <ArrowRight className="h-5 w-5 ml-2" />
                </Button>
                <Button
                  onClick={() => { setGodModePath(true); setStep(5) }}
                  className="flex-1 h-12 bg-gradient-to-r from-violet-600 to-fuchsia-500 hover:from-violet-500 hover:to-fuchsia-400 text-white font-semibold text-sm"
                >
                  <Shield className="h-5 w-5 mr-2" />
                  ⚡ Режим Бога
                </Button>
              </div>
            </motion.div>
          )}

          {fetchRefreshing && !fetchDone && (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 text-amber-400 animate-spin" />
                <span className="text-sm text-slate-300">Загрузка тиражей (фоновый режим)...</span>
              </div>
              <Progress className="h-2 bg-white/10" />
              <p className="text-[11px] text-slate-500">
                Это может занять несколько минут
                {fetchRefreshElapsed > 0 && (
                  <span className="text-amber-400"> · {Math.round(fetchRefreshElapsed / 1000)}с</span>
                )}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
