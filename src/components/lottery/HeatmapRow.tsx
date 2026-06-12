'use client'

import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { HeatmapEntry } from './types'

export function HeatmapRow({ entry, bgColor, bestModel }: { entry: HeatmapEntry; bgColor: string; bestModel?: { name: string; hits: number } }) {
  const [expanded, setExpanded] = useState(false)
  const predB1Set = new Set(entry.pred_b1 || [])
  const predB2Set = new Set(entry.pred_b2 || [])
  return (
    <div>
      <button onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className={`w-full flex items-center gap-2 text-[10px] p-1.5 rounded border ${bgColor} hover:brightness-110 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500`}>
        <span className="font-mono w-10 text-right shrink-0 opacity-70">#{entry.draw_no}</span>
        {entry.date && <span className="text-[9px] text-slate-500 w-16 shrink-0">{entry.date}</span>}
        <div className="flex gap-0.5 flex-1 min-w-0 flex-wrap">
          {/* v26.2: Block 1 label + all numbers */}
          <span className="text-[8px] text-blue-400/60 shrink-0 mr-0.5">Б1:</span>
          {(entry.act_b1 || []).map((n, j) => (
            <span key={`b1-${j}`} className={`min-w-5 h-4 flex items-center justify-center rounded text-[9px] font-mono ${predB1Set.has(n) ? 'bg-emerald-500/40 text-emerald-200' : 'bg-white/5 text-slate-500'}`}>
              {n}
            </span>
          ))}
          {/* v26.2: Block 2 label + all numbers */}
          {(entry.act_b2 || []).length > 0 && (
            <>
              <span className="text-slate-600 text-[8px] mx-0.5 shrink-0">|</span>
              <span className="text-[8px] text-emerald-400/60 shrink-0 mr-0.5">Б2:</span>
              {(entry.act_b2 || []).map((n, j) => (
                <span key={`b2-${j}`} className={`min-w-5 h-4 flex items-center justify-center rounded text-[9px] font-mono ${predB2Set.has(n) ? 'bg-emerald-500/40 text-emerald-200' : 'bg-white/5 text-slate-500'}`}>
                  {n}
                </span>
              ))}
            </>
          )}
        </div>
        <Badge variant="outline" className="text-[9px] border-current/30 shrink-0 min-w-5 justify-center">
          {entry.total}
        </Badge>
        <ChevronRight className={`h-3 w-3 shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      {expanded && (
        <div className="ml-12 mt-1 p-2 rounded bg-white/5 text-[10px] space-y-1">
          <div className="flex gap-4">
            <div><span className="text-blue-400">Блок 1 — Предсказание:</span> <span className="font-mono text-blue-300">{(entry.pred_b1 || []).join(', ')}</span></div>
            {entry.hits_b1 > 0 && <span className="text-emerald-400 font-mono">+{entry.hits_b1} попад.</span>}
          </div>
          <div className="flex gap-4">
            <div><span className="text-blue-400">Блок 1 — Реальный:</span> <span className="font-mono text-white">{(entry.act_b1 || []).join(', ')}</span></div>
          </div>
          {(entry.pred_b2 || []).length > 0 && (
            <div className="flex gap-4">
              <div><span className="text-emerald-400">Блок 2 — Предсказание:</span> <span className="font-mono text-emerald-300">{(entry.pred_b2 || []).join(', ')}</span></div>
              {entry.hits_b2 > 0 && <span className="text-emerald-400 font-mono">+{entry.hits_b2} попад.</span>}
            </div>
          )}
          {(entry.act_b2 || []).length > 0 && (
            <div className="flex gap-4">
              <div><span className="text-emerald-400">Блок 2 — Реальный:</span> <span className="font-mono text-white">{(entry.act_b2 || []).join(', ')}</span></div>
            </div>
          )}
          {bestModel && (
            <div><span className="text-slate-500">Лучшая модель:</span> <span className="text-emerald-400">{bestModel.name}</span> <span className="text-slate-500">({bestModel.hits} попад.)</span></div>
          )}
        </div>
      )}
    </div>
  )
}
