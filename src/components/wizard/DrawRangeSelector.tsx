'use client'

import { useState, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Info, RotateCcw } from 'lucide-react'

const PRESETS = [
  { label: '50', value: 50 },
  { label: '100', value: 100 },
  { label: '200', value: 200 },
  { label: '500', value: 500 },
  { label: '1000', value: 1000 },
  { label: 'Все', value: 0 },
] as const

interface DrawRangeSelectorProps {
  totalDraws: number
  drawRange?: { first: number; last: number; total: number } | null
  rangeFrom: number | null
  rangeTo: number | null
  onRangeChange: (from: number | null, to: number | null) => void
}

export function DrawRangeSelector({ totalDraws, drawRange, rangeFrom, rangeTo, onRangeChange }: DrawRangeSelectorProps) {
  const [mode, setMode] = useState<'preset' | 'manual'>('preset')
  const [manualFrom, setManualFrom] = useState('')
  const [manualTo, setManualTo] = useState('')

  const effectiveTotal = drawRange?.total ?? totalDraws ?? 0

  const selectedRange = useMemo(() => {
    if (rangeFrom == null && rangeTo == null) return null
    return { from: rangeFrom ?? 1, to: rangeTo ?? effectiveTotal }
  }, [rangeFrom, rangeTo, effectiveTotal])

  const activePreset = useMemo(() => {
    if (!selectedRange) return null
    if (selectedRange.from === 1 && selectedRange.to === effectiveTotal) return 0
    const count = selectedRange.to - selectedRange.from + 1
    const preset = PRESETS.find(p => p.value === count && p.value > 0)
    return preset ? preset.value : null
  }, [selectedRange, effectiveTotal])

  const handlePreset = (value: number) => {
    if (value === 0 || value >= effectiveTotal) {
      onRangeChange(null, null)
    } else {
      onRangeChange(effectiveTotal - value + 1, effectiveTotal)
    }
  }

  const handleApplyManual = () => {
    const from = parseInt(manualFrom) || null
    const to = parseInt(manualTo) || null
    onRangeChange(from, to)
  }

  const handleReset = () => {
    setManualFrom('')
    setManualTo('')
    onRangeChange(null, null)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-slate-300">Диапазон тиражей:</span>
        {selectedRange && (
          <Badge variant="outline" className="text-[9px] border-violet-500/30 text-violet-400">
            {selectedRange.from}–{selectedRange.to} ({selectedRange.to - selectedRange.from + 1} тиражей)
          </Badge>
        )}
        {selectedRange && (
          <button onClick={handleReset} className="text-slate-500 hover:text-slate-300 transition-colors">
            <RotateCcw className="h-3 w-3" />
          </button>
        )}
      </div>

      <div className="flex gap-1.5 flex-wrap">
        {PRESETS.map((p) => {
          const isActive = activePreset === p.value || (!activePreset && p.value === 0 && !selectedRange)
          return (
            <Button
              key={p.label}
              variant="outline"
              size="sm"
              onClick={() => handlePreset(p.value)}
              disabled={p.value > effectiveTotal}
              className={`h-7 px-2.5 text-[10px] transition-all ${
                isActive
                  ? 'border-violet-500/50 text-violet-300 bg-violet-500/10'
                  : 'border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-300'
              }`}
            >
              {p.label}
            </Button>
          )
        })}
      </div>

      <button
        onClick={() => setMode(mode === 'preset' ? 'manual' : 'preset')}
        className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
      >
        {mode === 'preset' ? '→ Ручной ввод' : '→ Пресеты'}
      </button>

      {mode === 'manual' && (
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder="От №"
            value={manualFrom}
            onChange={(e) => setManualFrom(e.target.value)}
            className="h-7 w-24 rounded-md border border-white/10 bg-white/5 px-2 text-[10px] text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
          />
          <span className="text-slate-500 text-xs">—</span>
          <input
            type="number"
            placeholder="До №"
            value={manualTo}
            onChange={(e) => setManualTo(e.target.value)}
            className="h-7 w-24 rounded-md border border-white/10 bg-white/5 px-2 text-[10px] text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
          />
          <Button onClick={handleApplyManual} size="sm" className="h-7 px-3 text-[10px] bg-violet-600 hover:bg-violet-500">
            Применить
          </Button>
        </div>
      )}

      {drawRange && (
        <div className="flex items-center gap-1 text-[9px] text-slate-600">
          <Info className="h-2.5 w-2.5" />
          Доступно тиражей: {drawRange.first}–{drawRange.last} ({drawRange.total})
        </div>
      )}
    </div>
  )
}
