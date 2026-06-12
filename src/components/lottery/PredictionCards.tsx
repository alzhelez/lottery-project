'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Shield, Layers, Flame, TrendingUp, BarChart3,
  GitBranch, CheckCircle2, AlertTriangle, Clock,
} from 'lucide-react'
import { BLOCK_COLOR_CLASSES } from './types'
import { HeatmapRow } from './HeatmapRow'
import type { PredictionResult, HeatmapEntry } from './types'

// ── TopModelsCard ──────────────────────────────────────────────────────────

export function TopModelsCard({ predictResult }: { predictResult: PredictionResult }) {
  const hasTopModels = !!(predictResult.prediction as Record<string, unknown>)?.top_model_1
  if (!hasTopModels) return null

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <Shield className="h-3.5 w-3.5 text-emerald-400" />
          Топ-5 лучших моделей по попаданиям
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-xs text-slate-500 mb-2">Модели с наивысшей средней точностью на последних тиражах:</div>
        <div className="space-y-2">
          {([1, 2, 3, 4, 5] as const).map((rank) => {
            const model = (predictResult.prediction as Record<string, unknown>)[`top_model_${rank}`] as
              { name: string; score: number; b1: number[]; b2: number[] } | undefined
            if (!model) return null
            return (
              <div key={rank} className="flex items-center gap-2">
                <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-400 shrink-0 w-6 justify-center">
                  {rank}
                </Badge>
                <span className="text-xs text-slate-300 truncate flex-1">{model.name}</span>
                <span className="text-[10px] font-mono text-emerald-400">
                  {model.score != null ? model.score.toFixed(2) : '—'}
                </span>
                <div className="flex gap-0.5 flex-wrap">
                  <span className="text-[8px] text-blue-400/60 self-center mr-0.5">Б1:</span>
                  {model.b1.map((n, j) => (
                    <span
                      key={`m${rank}-b1-${j}`}
                      className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-blue-500/15 text-blue-300"
                    >
                      {n}
                    </span>
                  ))}
                  {model.b2.length > 0 && (
                    <>
                      <span className="text-slate-600 mx-0.5">+</span>
                      <span className="text-[8px] text-emerald-400/60 self-center mr-0.5">Б2:</span>
                    </>
                  )}
                  {model.b2.map((n, j) => (
                    <span
                      key={`m${rank}-b2-${j}`}
                      className="inline-flex items-center h-5 min-w-5 justify-center rounded text-[9px] font-mono bg-emerald-500/15 text-emerald-300"
                    >
                      {n}
                    </span>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

// ── HeatmapCard ────────────────────────────────────────────────────────────

export function HeatmapCard({ predictResult }: { predictResult: PredictionResult }) {
  const _hm = ((predictResult.backtest as Record<string, unknown>)?.['heatmap'] || []) as HeatmapEntry[]
  if (!Array.isArray(_hm) || _hm.length === 0) return null

  const hmSlice = _hm.slice(0, 20)
  const hmMaxHits = Math.max(...hmSlice.map((e) => e.total), 1)

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <Flame className="h-3.5 w-3.5 text-orange-400" />
          Тепловая карта попаданий (последние 20)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {hmSlice.map((entry, i) => {
            const intensity = entry.total / hmMaxHits
            const bgColor =
              intensity > 0.7
                ? 'bg-emerald-500/30 text-emerald-300 border-emerald-500/30'
                : intensity > 0.4
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/20'
                  : 'bg-white/5 text-slate-400 border-white/10'
            const bestModel = (entry as Record<string, unknown>).best_model as
              | { name: string; hits: number }
              | undefined
            return <HeatmapRow key={i} entry={entry} bgColor={bgColor} bestModel={bestModel} />
          })}
        </div>
      </CardContent>
    </Card>
  )
}

// ── PairAnalysisCard ───────────────────────────────────────────────────────

export function PairAnalysisCard({ predictResult }: { predictResult: PredictionResult }) {
  const pa = predictResult.pair_analysis
  if (!pa?.pairs?.length) return null

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <Flame className="h-3.5 w-3.5 text-orange-400" />
          Топ-10 частых пар чисел (Блок 1)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-[10px] text-slate-500 mb-2">Пары, которые чаще всего выпадают вместе:</div>
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {pa.pairs.slice(0, 10).map((p, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="text-[10px] text-slate-500 w-4 text-right">{i + 1}.</span>
              <div className="flex gap-1">
                {p.pair.map((n, ni) => (
                  <Badge key={ni} variant="outline" className="text-[10px] border-orange-500/30 text-orange-300 px-1.5 py-0">
                    {n}
                  </Badge>
                ))}
              </div>
              <span className="ml-auto font-mono text-[10px] text-slate-400">{p.count}×</span>
              {p.last_seen <= 5 && <span className="text-[9px] text-emerald-400">недавно</span>}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ── GapAnalysisCard ────────────────────────────────────────────────────────

export function GapAnalysisCard({ predictResult }: { predictResult: PredictionResult }) {
  const ga = predictResult.gap_analysis
  if (!ga?.block1?.length) return null

  const overdueB1 = ga.block1.filter((n) => n.overdue_score > 0.5).slice(0, 8)
  if (!overdueB1.length) return null

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <TrendingUp className="h-3.5 w-3.5 text-amber-400" />
          Просроченные числа (Блок 1)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-[10px] text-slate-500 mb-2">Числа, которые не выпадали дольше обычного:</div>
        <div className="flex flex-wrap gap-1.5">
          {overdueB1.map((n) => (
            <div key={n.number} className="flex items-center gap-1 px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/20">
              <span className="text-xs font-mono font-bold text-amber-300">{n.number}</span>
              <span className="text-[9px] text-slate-500">{n.gap} тир.</span>
              {n.avg_gap && <span className="text-[9px] text-slate-600">(ср. {n.avg_gap})</span>}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ── NumberSpectrumCard ─────────────────────────────────────────────────────

export function NumberSpectrumCard({ predictResult }: { predictResult: PredictionResult }) {
  const votesB1 = predictResult.consensusVotesB1
  const votesB2 = predictResult.consensusVotesB2
  if (!votesB1 || Object.keys(votesB1).length === 0) return null

  const predB1 = new Set(predictResult.prediction.block1)
  const predB2 = new Set(predictResult.prediction.block2)
  const maxVotes = Math.max(...Object.values(votesB1), ...(votesB2 ? Object.values(votesB2) : []), 1)

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <Layers className="h-3.5 w-3.5 text-blue-400" />
          Полный спектр чисел (голоса моделей)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {(['block1', 'block2'] as const).map((block) => {
          const votes = block === 'block1' ? votesB1 : votesB2
          const predSet = block === 'block1' ? predB1 : predB2
          const label = block === 'block1' ? 'Блок 1' : 'Блок 2'
          const color = block === 'block1' ? 'blue' : 'emerald'
          if (!votes || Object.keys(votes).length === 0) return null
          const sortedNums = Object.entries(votes).sort(([, a], [, b]) => b - a)
          return (
            <div key={block}>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">{label}</p>
                <span className="text-[9px] text-slate-500">{sortedNums.length} чисел</span>
              </div>
              <div className="flex flex-wrap gap-1 max-h-36 overflow-y-auto">
                {sortedNums.map(([numStr, votes]) => {
                  const num = parseInt(numStr)
                  const isPredicted = predSet.has(num)
                  return (
                    <div
                      key={num}
                      className={`inline-flex flex-col items-center rounded-md px-1.5 py-1 min-w-[32px] ${
                        isPredicted
                          ? `${BLOCK_COLOR_CLASSES[color]?.bg || ''} border ${BLOCK_COLOR_CLASSES[color]?.border || ''}`
                          : 'bg-white/[0.03] border border-white/5'
                      }`}
                    >
                      <span
                        className={`text-[10px] font-mono font-bold ${
                          isPredicted ? (BLOCK_COLOR_CLASSES[color]?.text || 'text-slate-400') : 'text-slate-400'
                        }`}
                      >
                        {num}
                      </span>
                      <span className="text-[8px] text-slate-500">{votes}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
        <div className="flex gap-3 text-[9px] text-slate-500 pt-1 border-t border-white/5">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-blue-500/40" /> В прогнозе (Б1)
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500/40" /> В прогнозе (Б2)
          </span>
          <span className="text-slate-600">Число = голоса моделей</span>
        </div>
      </CardContent>
    </Card>
  )
}

// ── CrossGameCard ───────────────────────────────────────────────────────────

export function CrossGameCard({ predictResult }: { predictResult: PredictionResult }) {
  const cg = predictResult.cross_game as
    | {
        hot_numbers?: number[]
        source_games?: string[]
        method?: string
        number_stats?: { number: number; count: number; expected?: number; ratio?: number }[]
      }
    | undefined
  if (!cg) return null

  const hasHotNumbers = cg.hot_numbers && cg.hot_numbers.length > 0
  const hasSourceGames = cg.source_games && cg.source_games.length > 0
  const hasNumberStats = cg.number_stats && cg.number_stats.length > 0
  if (!hasHotNumbers && !hasSourceGames && !hasNumberStats) return null

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <GitBranch className="h-3.5 w-3.5 text-cyan-400" />
          Кросс-игровой анализ
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Source Games */}
        {hasSourceGames && (
          <div>
            <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Игры-источники</p>
            <div className="flex flex-wrap gap-1">
              {cg.source_games!.map((g) => (
                <Badge key={g} variant="outline" className="text-[9px] border-cyan-500/30 text-cyan-300">
                  {g}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Hot Numbers */}
        {hasHotNumbers && (
          <div>
            <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Горячие числа</p>
            <div className="flex flex-wrap gap-1">
              {cg.hot_numbers!.map((n) => (
                <Badge key={n} variant="outline" className="text-[9px] border-red-500/30 text-red-300">
                  {n}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Number Stats */}
        {hasNumberStats && (
          <div>
            <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Статистика чисел</p>
            <div className="space-y-0.5 max-h-32 overflow-y-auto">
              {cg.number_stats!.slice(0, 10).map((s) => (
                <div key={s.number} className="flex items-center gap-2 text-[10px]">
                  <span className="w-5 h-5 rounded text-[9px] font-mono flex items-center justify-center bg-white/5 text-slate-400">
                    {s.number}
                  </span>
                  <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-cyan-500"
                      style={{ width: `${Math.min((s.count || 0) * 2, 100)}%` }}
                    />
                  </div>
                  <span className="font-mono text-slate-400 w-8 text-right">{s.count}×</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Method */}
        {cg.method && (
          <p className="text-[9px] text-slate-500 pt-1 border-t border-white/5">Метод: {cg.method}</p>
        )}
      </CardContent>
    </Card>
  )
}

// ── DrawScheduleCard ────────────────────────────────────────────────────────

export function DrawScheduleCard({ predictResult }: { predictResult: PredictionResult }) {
  const ds = predictResult.draw_schedule
  if (!ds) return null

  return (
    <Card className={`border ${ds.is_predictable ? 'border-emerald-500/30' : 'border-amber-500/30'} bg-white/5`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-blue-400" />
          Следующий тираж
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-white/5 p-3 text-center">
            <div className="text-[10px] text-slate-400 mb-1">Номер тиража</div>
            <div className="text-lg font-bold text-white">#{ds.next_number || '—'}</div>
          </div>
          <div className="rounded-lg bg-white/5 p-3 text-center">
            <div className="text-[10px] text-slate-400 mb-1">Время</div>
            <div className="text-sm font-bold text-white">{ds.estimated_time || '—'}</div>
          </div>
        </div>
        <div className={`rounded-lg p-3 ${ds.is_predictable ? 'bg-emerald-500/10' : 'bg-amber-500/10'}`}>
          <div className="flex items-center gap-2 text-xs">
            {ds.is_predictable ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                <span className="text-emerald-300">
                  {ds.draw_type_label || 'Генератор случайных чисел — прогноз возможен'}
                </span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                <span className="text-amber-300">
                  {ds.draw_type_label || 'Телевизионный стенд — прогноз ограничен'}
                </span>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── FrequencyAnalysisCard ───────────────────────────────────────────────────

export function FrequencyAnalysisCard({ predictResult }: { predictResult: PredictionResult }) {
  const fa = predictResult.frequency_analysis
  if (!fa?.block1?.length) return null

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <BarChart3 className="h-3.5 w-3.5 text-cyan-400" />
          Частота выпаданий чисел
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {(['block1', 'block2'] as const).map((block) => {
          const nums = fa[block]
          if (!nums?.length) return null
          const label = block === 'block1' ? 'Блок 1' : 'Блок 2'
          const maxCount = Math.max(...nums.map((n) => n.count), 1)
          return (
            <div key={block}>
              <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">{label}</p>
              <div className="space-y-0.5 max-h-40 overflow-y-auto">
                {nums.slice(0, 15).map((n) => (
                  <div key={n.number} className="flex items-center gap-2 text-[10px]">
                    <span
                      className={`w-5 h-5 rounded text-[9px] font-mono flex items-center justify-center ${
                        n.last_seen <= 3 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/5 text-slate-400'
                      }`}
                    >
                      {n.number}
                    </span>
                    <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-cyan-500"
                        style={{ width: `${(n.count / maxCount) * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-slate-400 w-8 text-right">{n.count}×</span>
                    {n.last_seen <= 3 && <span className="text-[9px] text-emerald-400">недавно</span>}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

// ── SumRangeStatsCard ───────────────────────────────────────────────────────

export function SumRangeStatsCard({ predictResult }: { predictResult: PredictionResult }) {
  const srs = predictResult.sum_range_stats as Record<string, Record<string, unknown>> | undefined
  if (!srs?.block1) return null
  const b1 = srs.block1
  const b2 = srs.block2
  if (!b1 || !('mean' in b1)) return null

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs flex items-center gap-2">
          <BarChart3 className="h-3.5 w-3.5 text-amber-400" />
          Статистика сумм и размахов
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Block 1 */}
        <div>
          <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Блок 1</p>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-amber-500/10 p-2.5 text-center">
              <div className="text-[10px] text-slate-400 mb-0.5">Средняя сумма</div>
              <div className="text-sm font-bold text-amber-300">{b1.mean ?? '—'}</div>
            </div>
            <div className="rounded-lg bg-amber-500/10 p-2.5 text-center">
              <div className="text-[10px] text-slate-400 mb-0.5">σ суммы</div>
              <div className="text-sm font-bold text-amber-300">{b1.std ?? '—'}</div>
            </div>
            {b1.range_mean != null && (
              <div className="rounded-lg bg-white/5 p-2.5 text-center">
                <div className="text-[10px] text-slate-400 mb-0.5">Ср. размах</div>
                <div className="text-sm font-bold text-white">{b1.range_mean}</div>
              </div>
            )}
            {b1.range_std != null && (
              <div className="rounded-lg bg-white/5 p-2.5 text-center">
                <div className="text-[10px] text-slate-400 mb-0.5">σ размаха</div>
                <div className="text-sm font-bold text-white">{b1.range_std}</div>
              </div>
            )}
            {b1.p5 != null && (
              <div className="rounded-lg bg-white/5 p-2.5 text-center">
                <div className="text-[10px] text-slate-400 mb-0.5">Сумма P5</div>
                <div className="text-sm font-bold text-white">{b1.p5}</div>
              </div>
            )}
            {b1.p95 != null && (
              <div className="rounded-lg bg-white/5 p-2.5 text-center">
                <div className="text-[10px] text-slate-400 mb-0.5">Сумма P95</div>
                <div className="text-sm font-bold text-white">{b1.p95}</div>
              </div>
            )}
          </div>
        </div>
        {/* Block 2 */}
        {b2 && 'mean' in b2 && (
          <div>
            <p className="text-[10px] text-slate-400 mb-1.5 font-medium uppercase tracking-wider">Блок 2</p>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-amber-500/10 p-2.5 text-center">
                <div className="text-[10px] text-slate-400 mb-0.5">Средняя сумма</div>
                <div className="text-sm font-bold text-amber-300">{b2.mean ?? '—'}</div>
              </div>
              <div className="rounded-lg bg-amber-500/10 p-2.5 text-center">
                <div className="text-[10px] text-slate-400 mb-0.5">σ суммы</div>
                <div className="text-sm font-bold text-amber-300">{b2.std ?? '—'}</div>
              </div>
              {b2.p5 != null && (
                <div className="rounded-lg bg-white/5 p-2.5 text-center">
                  <div className="text-[10px] text-slate-400 mb-0.5">Сумма P5</div>
                  <div className="text-sm font-bold text-white">{b2.p5}</div>
                </div>
              )}
              {b2.p95 != null && (
                <div className="rounded-lg bg-white/5 p-2.5 text-center">
                  <div className="text-[10px] text-slate-400 mb-0.5">Сумма P95</div>
                  <div className="text-sm font-bold text-white">{b2.p95}</div>
                </div>
              )}
            </div>
          </div>
        )}
        <div className="text-[9px] text-slate-500 pt-1 border-t border-white/5">
          {b1.count ? `На основе ${b1.count} тиражей` : 'Исторические данные'}
        </div>
      </CardContent>
    </Card>
  )
}
