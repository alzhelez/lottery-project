'use client'

import { Card, CardContent } from '@/components/ui/card'
import { CalendarRange, Info } from 'lucide-react'
import type { DrawRange } from './types'

interface DrawRangeSelectorProps {
  drawRange: DrawRange | null
  rangeFrom: number | null
  rangeTo: number | null
  seedSize: number
  setRangeFrom: (v: number | null) => void
  setRangeTo: (v: number | null) => void
  setSeedSize: (v: number) => void
}

const PRESETS = [
  { label: 'Все', from: null as number | null, to: null as number | null },
  { label: 'Последние 50', from: null, to: 50 },
  { label: 'Последние 100', from: null, to: 100 },
  { label: 'Последние 200', from: null, to: 200 },
  { label: 'Последние 500', from: null, to: 500 },
  { label: 'Последние 1000', from: null, to: 1000 },
]

function getDrawsInRange(drawRange: DrawRange | null, from: number | null, to: number | null): number {
  if (!drawRange) return 0
  const actualFrom = from ?? drawRange.firstDrawNo
  const actualTo = to ?? drawRange.lastDrawNo
  return Math.max(0, actualTo - actualFrom + 1)
}

export function DrawRangeSelector({
  drawRange,
  rangeFrom,
  rangeTo,
  seedSize,
  setRangeFrom,
  setRangeTo,
  setSeedSize,
}: DrawRangeSelectorProps) {
  if (!drawRange) return null

  const lastNo = drawRange.lastDrawNo
  const nextDrawNo = lastNo + 1
  const drawsInRange = getDrawsInRange(drawRange, rangeFrom, rangeTo)
  const effectiveFrom = rangeFrom ?? drawRange.firstDrawNo
  const effectiveTo = rangeTo ?? drawRange.lastDrawNo

  // If "to" is set as a relative count (e.g., "last 100"), convert to absolute
  const displayFrom = rangeFrom ?? drawRange.firstDrawNo
  const displayTo = rangeTo ?? drawRange.lastDrawNo

  return (
    <Card className="border-white/10 bg-white/5 backdrop-blur-sm">
      <CardContent className="py-4 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <CalendarRange className="h-4 w-4 text-blue-400" />
          <span className="text-xs font-medium text-white">Выбор диапазона тиражей</span>
        </div>

        {/* Hint: next draw number */}
        <div className="flex items-start gap-2 rounded-lg bg-blue-500/10 p-2.5">
          <Info className="h-3.5 w-3.5 text-blue-400 mt-0.5 shrink-0" />
          <p className="text-[11px] text-blue-300 leading-relaxed">
            Данные: {drawRange.total} тиражей (#{drawRange.firstDrawNo}–#{drawRange.lastDrawNo}).
            Прогноз на тираж <span className="font-bold text-blue-200">№{nextDrawNo}</span>
          </p>
        </div>

        {/* Presets */}
        <div>
          <p className="text-[10px] text-slate-500 mb-2 uppercase tracking-wider">Быстрый выбор</p>
          <div className="flex flex-wrap gap-1.5">
            {PRESETS.map((p) => {
              const isActive = rangeFrom === p.from && rangeTo === p.to
              return (
                <button
                  key={p.label}
                  onClick={() => { setRangeFrom(p.from); setRangeTo(p.to) }}
                  className={`px-2.5 py-1 text-[11px] rounded-md border transition-colors ${
                    isActive
                      ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                      : 'bg-white/5 border-white/10 text-slate-400 hover:bg-white/10 hover:text-slate-300'
                  }`}
                >
                  {p.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Manual range input */}
        <div>
          <p className="text-[10px] text-slate-500 mb-2 uppercase tracking-wider">Ручной ввод диапазона</p>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <label className="text-[11px] text-slate-400">От №</label>
              <input
                type="number"
                min={drawRange.firstDrawNo}
                max={drawRange.lastDrawNo}
                placeholder={String(drawRange.firstDrawNo)}
                value={rangeFrom ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  setRangeFrom(v === '' ? null : Math.max(drawRange.firstDrawNo, Math.min(drawRange.lastDrawNo, Number(v))))
                }}
                className="w-20 rounded-md border border-white/20 bg-white/5 text-white text-xs px-2 py-1.5 focus:ring-blue-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              />
            </div>
            <span className="text-slate-600">—</span>
            <div className="flex items-center gap-1.5">
              <label className="text-[11px] text-slate-400">До №</label>
              <input
                type="number"
                min={drawRange.firstDrawNo}
                max={drawRange.lastDrawNo}
                placeholder={String(drawRange.lastDrawNo)}
                value={rangeTo ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  setRangeTo(v === '' ? null : Math.max(drawRange.firstDrawNo, Math.min(drawRange.lastDrawNo, Number(v))))
                }}
                className="w-20 rounded-md border border-white/20 bg-white/5 text-white text-xs px-2 py-1.5 focus:ring-blue-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="flex items-center justify-between text-[11px] rounded-lg bg-white/5 px-3 py-2">
          <span className="text-slate-400">
            Тиражей в диапазоне: <span className="text-white font-mono font-bold">#{displayFrom}–#{displayTo}</span>
          </span>
          <span className="text-slate-300 font-mono">{drawsInRange}</span>
        </div>

        {/* Seed size (training subset) */}
        <div>
          <label className="flex items-center gap-2 text-[11px] text-slate-400 cursor-pointer select-none">
            <span>Размер обучающей выборки:</span>
            <select
              value={seedSize}
              onChange={(e) => setSeedSize(Number(e.target.value))}
              className="rounded border border-white/20 bg-white/5 text-white text-[11px] px-2 py-1 focus:ring-blue-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <option value={50} className="bg-slate-800 text-white">50 тиражей</option>
              <option value={100} className="bg-slate-800 text-white">100 тиражей</option>
              <option value={200} className="bg-slate-800 text-white">200 тиражей</option>
              <option value={500} className="bg-slate-800 text-white">500 тиражей</option>
              <option value={1000} className="bg-slate-800 text-white">1000 тиражей</option>
            </select>
          </label>
        </div>
      </CardContent>
    </Card>
  )
}
