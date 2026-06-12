'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  ReferenceLine,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// ---------------------------------------------------------------------------
// Shared dark-theme tooltip style
// ---------------------------------------------------------------------------

const tooltipStyle: React.CSSProperties = {
  backgroundColor: 'rgba(15, 23, 42, 0.92)',
  border: '1px solid rgba(148, 163, 184, 0.15)',
  borderRadius: '8px',
  padding: '8px 12px',
  fontSize: '12px',
  color: '#e2e8f0',
}

const axisTickStyle = { fontSize: 10, fill: '#94a3b8' }

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

function getAccentFill(color: 'blue' | 'emerald', opacity = 0.75) {
  return color === 'blue'
    ? `rgba(59, 130, 246, ${opacity})`
    : `rgba(16, 185, 129, ${opacity})`
}

function getAccentStroke(color: 'blue' | 'emerald') {
  return color === 'blue' ? '#3b82f6' : '#10b981'
}

/** Returns a palette of semi-transparent colors for the pie chart. */
function getPiePalette(
  color: 'blue' | 'emerald',
  count: number,
): string[] {
  const bases =
    color === 'blue'
      ? [
          [59, 130, 246],   // blue-500
          [96, 165, 250],   // blue-400
          [147, 197, 253],  // blue-300
          [129, 140, 248],  // indigo-400
          [34, 211, 238],   // cyan-400
          [56, 189, 248],   // sky-400
          [99, 102, 241],   // indigo-500
          [167, 139, 250],  // violet-400
          [45, 212, 191],   // teal-400
          [52, 211, 153],   // emerald-400
        ]
      : [
          [16, 185, 129],   // emerald-500
          [52, 211, 153],   // emerald-400
          [110, 231, 183],  // emerald-300
          [34, 211, 238],   // cyan-400
          [56, 189, 248],   // sky-400
          [45, 212, 191],   // teal-400
          [74, 222, 128],   // green-400
          [129, 140, 248],  // indigo-400
          [167, 139, 250],  // violet-400
          [251, 191, 36],   // amber-400
        ]

  return Array.from({ length: count }, (_, i) => {
    const [r, g, b] = bases[i % bases.length]
    return `rgba(${r}, ${g}, ${b}, 0.78)`
  })
}

// ---------------------------------------------------------------------------
// Custom tooltip renderers
// ---------------------------------------------------------------------------

interface FreqTooltipPayload {
  number: number
  count: number
  last_seen: number
}

function FrequencyBarTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: FreqTooltipPayload }>
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={tooltipStyle}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Число {d.number}</div>
      <div>Появлений: <span style={{ color: '#60a5fa' }}>{d.count}</span></div>
      <div>Последнее: тираж <span style={{ color: '#94a3b8' }}>#{d.last_seen}</span></div>
    </div>
  )
}

function AccuracyTimelineTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ value: number }>
  label?: string | number
}) {
  if (!active || !payload?.length) return null
  return (
    <div style={tooltipStyle}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Тираж #{label}</div>
      <div>Совпадений: <span style={{ color: '#60a5fa' }}>{payload[0].value}</span></div>
    </div>
  )
}

function ConsensusPieTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ name: string; value: number; payload: { percent: number } }>
}) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div style={tooltipStyle}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Число {d.name}</div>
      <div>
        Голосов: <span style={{ color: '#60a5fa' }}>{d.value}</span>
      </div>
      <div>
        Доля:{' '}
        <span style={{ color: '#a78bfa' }}>
          {(d.payload.percent * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  )
}

// ===================================================================
// 1. FrequencyBarChart
// ===================================================================

export interface FrequencyBarChartProps {
  data: Array<{ number: number; count: number; last_seen: number }>
  title: string
  maxItems?: number
  accentColor?: 'blue' | 'emerald'
}

export function FrequencyBarChart({
  data,
  title,
  maxItems = 20,
  accentColor = 'blue',
}: FrequencyBarChartProps) {
  if (!data?.length) return null

  const sorted = [...data]
    .sort((a, b) => b.count - a.count)
    .slice(0, maxItems)

  // Reverse so the highest bar is at the top in the horizontal layout
  const chartData = sorted
    .reverse()
    .map((d) => ({ ...d, numberStr: String(d.number) }))

  return (
    <Card className="border-white/[0.06] bg-white/[0.03]">
      <CardHeader className="pb-0">
        <CardTitle className="text-sm text-slate-200">{title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-2">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 16, bottom: 0, left: 48 }}
          >
            <XAxis
              type="number"
              tick={{ ...axisTickStyle }}
              axisLine={{ stroke: 'rgba(148,163,184,0.12)' }}
              tickLine={false}
            />
            <YAxis
              dataKey="numberStr"
              type="category"
              tick={{ ...axisTickStyle }}
              axisLine={false}
              tickLine={false}
              width={44}
            />
            <RechartsTooltip
              content={<FrequencyBarTooltip />}
              cursor={{ fill: 'rgba(148,163,184,0.06)' }}
            />
            <Bar
              dataKey="count"
              fill={getAccentFill(accentColor)}
              stroke={getAccentStroke(accentColor)}
              strokeWidth={1}
              radius={[0, 4, 4, 0]}
              barSize={12}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ===================================================================
// 2. AccuracyTimelineChart
// ===================================================================

export interface AccuracyTimelineChartProps {
  data: Array<{ draw_no: number; total: number; date?: string }>
  baselineRandom?: number
}

export function AccuracyTimelineChart({
  data,
  baselineRandom,
}: AccuracyTimelineChartProps) {
  if (!data?.length) return null

  // Show last 30 data points
  const chartData = data.slice(-30)

  return (
    <Card className="border-white/[0.06] bg-white/[0.03]">
      <CardHeader className="pb-0">
        <CardTitle className="text-sm text-slate-200">
          Точность предсказаний по тиражам
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-2">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart
            data={chartData}
            margin={{ top: 8, right: 16, bottom: 0, left: 28 }}
          >
            <XAxis
              dataKey="draw_no"
              tick={{ ...axisTickStyle, fontSize: 9 }}
              axisLine={{ stroke: 'rgba(148,163,184,0.12)' }}
              tickLine={false}
              allowDuplicatedCategory={false}
            />
            <YAxis
              tick={{ ...axisTickStyle }}
              axisLine={false}
              tickLine={false}
              width={24}
            />
            <RechartsTooltip
              content={<AccuracyTimelineTooltip />}
            />
            {baselineRandom != null && (
              <ReferenceLine
                y={baselineRandom}
                stroke="#f87171"
                strokeDasharray="6 3"
                strokeWidth={1.5}
                label={{
                  value: 'Базлайн',
                  position: 'insideTopRight',
                  fill: '#f87171',
                  fontSize: 10,
                }}
              />
            )}
            <Line
              type="monotone"
              dataKey="total"
              stroke="#60a5fa"
              strokeWidth={2}
              dot={{ r: 3, fill: '#60a5fa', strokeWidth: 0 }}
              activeDot={{ r: 5, fill: '#93c5fd', strokeWidth: 2, stroke: '#1e3a5f' }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ===================================================================
// 3. ConsensusPieChart
// ===================================================================

export interface ConsensusPieChartProps {
  votes: Record<string, number>
  title: string
  maxItems?: number
  color?: 'blue' | 'emerald'
}

export function ConsensusPieChart({
  votes,
  title,
  maxItems = 15,
  color = 'blue',
}: ConsensusPieChartProps) {
  if (!votes || Object.keys(votes).length === 0) return null

  const entries = Object.entries(votes)
  const totalVotes = entries.reduce((s, [, v]) => s + v, 0)

  if (totalVotes === 0) return null

  const sorted = entries
    .sort((a, b) => b[1] - a[1])
    .slice(0, maxItems)

  const chartData = sorted.map(([number, value]) => ({
    name: number,
    value,
    percent: value / totalVotes,
  }))

  const palette = getPiePalette(color, chartData.length)

  return (
    <Card className="border-white/[0.06] bg-white/[0.03]">
      <CardHeader className="pb-0">
        <CardTitle className="text-sm text-slate-200">{title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-2">
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <RechartsTooltip
              content={<ConsensusPieTooltip />}
            />
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={105}
              paddingAngle={2}
              stroke="rgba(15, 23, 42, 0.6)"
              strokeWidth={1}
            >
              {chartData.map((_entry, idx) => (
                <Cell key={`cell-${idx}`} fill={palette[idx]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
