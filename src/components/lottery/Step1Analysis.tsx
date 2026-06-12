'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Activity, RefreshCw, AlertTriangle, Target } from 'lucide-react'
import { motion } from 'framer-motion'
import type { GameAnalysis, GameCategories } from './types'
import { fadeIn } from './types'

interface Step1AnalysisProps {
  analyzeLoading: boolean
  analyzeError: string | null
  games: GameAnalysis[]
  categories: GameCategories | null
  selectedGame: GameAnalysis | null
  runAnalyze: () => void
  handleSelectGame: (game: GameAnalysis) => void
}

export function Step1Analysis({
  analyzeLoading,
  analyzeError,
  games,
  categories,
  selectedGame,
  runAnalyze,
  handleSelectGame,
}: Step1AnalysisProps) {
  return (
    <motion.div key="step1" id="step-1" role="tabpanel" aria-labelledby="tab-1" {...fadeIn}>
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
        <div role="status" aria-live="polite" className="space-y-2">
          {[1, 2, 3, 4, 5].map(i => (
            <Skeleton key={i} className="h-8 w-full rounded-lg bg-white/10" />
          ))}
          <p className="text-center text-sm text-slate-400">
            <RefreshCw className="h-4 w-4 inline mr-2 animate-spin" />
            Сканирование файлов тиражей...
          </p>
        </div>
      )}

      {analyzeError && (
        <Card role="status" aria-live="polite" className="border-red-500/30 bg-red-500/5">
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

          {/* Redesigned: High anomaly + sorted list layout */}
          {(() => {
            // v26.2: Filter out games that redirect to other games (non-existent)
            const activeGames = games.filter(g => !g.redirect_target)
            const highAnomalyGames = activeGames.filter(g => g.score >= 50).sort((a, b) => b.score - a.score)
            const otherGames = activeGames.filter(g => g.score < 50).sort((a, b) => b.score - a.score)

            return (
              <>
                {/* High Anomaly Games — Prominent */}
                {highAnomalyGames.length > 0 && (
                  <div className="mb-4 space-y-2">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-bold text-red-400">🔴 Игры с высокой аномальностью</span>
                      <Badge variant="outline" className="text-[10px] border-red-500/30 text-red-400">
                        {highAnomalyGames.length}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {highAnomalyGames.map((game) => (
                        <motion.button key={game.key || game.name} variants={fadeIn}
                          role="option"
                          aria-selected={selectedGame?.key === game.key}
                          onClick={() => handleSelectGame(game)}
                          className={`text-left rounded-xl border-2 p-4 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                            selectedGame?.key === game.key
                              ? 'border-blue-500/50 bg-blue-500/10'
                              : 'border-red-500/30 bg-red-500/[0.06] hover:border-red-500/50 hover:bg-red-500/10'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-bold text-white">{game.name}</span>
                            <Badge className="bg-red-500/20 text-red-400 border-red-500/30 text-[10px]">
                              {game.score} баллов
                            </Badge>
                          </div>
                          <div className="flex items-center gap-4 text-xs text-slate-400">
                            <span>{game.draws} тиражей</span>
                            {game.chi2_p != null && <span>χ²={game.chi2_p}</span>}
                          </div>
                          {game.hot_numbers && game.hot_numbers.length > 0 && (
                            <div className="mt-2 flex gap-1">
                              {game.hot_numbers.slice(0, 5).map((n, i) => (
                                <span key={i} className="h-5 min-w-5 px-1 rounded text-[10px] font-mono bg-red-500/15 text-red-300 flex items-center justify-center">{n}</span>
                              ))}
                            </div>
                          )}
                        </motion.button>
                      ))}
                    </div>
                  </div>
                )}

                {/* All Other Games — Single sorted list */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-bold text-slate-300">Все остальные игры</span>
                    <span className="text-[10px] text-slate-500">по степени аномальности</span>
                    <Badge variant="outline" className="text-[10px] border-slate-500/30 text-slate-400">
                      {otherGames.length}
                    </Badge>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/[0.03] overflow-hidden">
                    <div className="max-h-96 overflow-y-auto custom-scrollbar-column">
                      {otherGames.map((game, i) => {
                        const scoreColor = game.score >= 40 ? 'text-red-400' : game.score >= 25 ? 'text-amber-400' : game.score >= 15 ? 'text-yellow-400' : game.score >= 5 ? 'text-emerald-400' : 'text-slate-500'
                        const barWidth = Math.max(game.score, 2)
                        const barColor = game.score >= 40 ? 'bg-red-500' : game.score >= 25 ? 'bg-amber-500' : game.score >= 15 ? 'bg-yellow-500' : 'bg-emerald-500'
                        return (
                          <button key={game.key || game.name}
                            role="option"
                            aria-selected={selectedGame?.key === game.key}
                            onClick={() => handleSelectGame(game)}
                            className={`w-full flex items-center gap-2 px-3 py-3 text-left border-b border-white/5 last:border-b-0 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 ${
                              selectedGame?.key === game.key ? 'bg-blue-500/10' : 'hover:bg-white/5'
                            }`}
                          >
                            <span className="text-[10px] text-slate-500 w-5 text-right">{i + 1}</span>
                            <span className="text-xs font-medium text-white truncate flex-1">{game.name}</span>
                            <div className="w-16 h-1.5 rounded-full bg-white/10 overflow-hidden shrink-0">
                              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${barWidth}%` }} />
                            </div>
                            <span className={`text-[11px] font-mono font-bold w-6 text-right ${scoreColor}`}>
                              {Math.round(game.score)}
                            </span>
                            <span className="text-[9px] text-slate-500 w-8 text-right">{game.draws}д</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </>
            )
          })()}
          <p className="text-center text-xs text-slate-500 mt-6">
            Нажмите на карточку игры, чтобы продолжить →
          </p>
        </>
      )}
    </motion.div>
  )
}
