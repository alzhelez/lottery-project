interface Series {
  name: string
  values: number[]
  color: string
  dashed?: boolean
}

/** Линии накопленного превышения над случайным выбором. Ноль — уровень случайности. */
export function LineChart({ series, height = 220, yLabel }: { series: Series[]; height?: number; yLabel?: string }) {
  const width = 720
  const pad = { l: 48, r: 12, t: 12, b: 24 }
  const all = series.flatMap((s) => s.values)
  if (all.length === 0) return null
  const max = Math.max(1, ...all)
  const min = Math.min(-1, ...all)
  const len = Math.max(...series.map((s) => s.values.length))
  const x = (i: number) => pad.l + (i / Math.max(1, len - 1)) * (width - pad.l - pad.r)
  const y = (v: number) => pad.t + ((max - v) / (max - min)) * (height - pad.t - pad.b)
  const ticks = [max, (max + min) / 2, min].map((v) => Math.round(v))
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={yLabel ?? 'график'}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={width - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="tick">{t}</text>
          </g>
        ))}
        <line x1={pad.l} x2={width - pad.r} y1={y(0)} y2={y(0)} className="zero" />
        {series.map((s) => (
          <polyline key={s.name} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dashed ? '5 4' : undefined}
            points={s.values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')} />
        ))}
      </svg>
      <figcaption className="legend">
        {series.map((s) => (
          <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>
        ))}
      </figcaption>
    </figure>
  )
}

/** Частоты чисел против ожидаемой при честной лотерее (пунктир). */
export function FreqBars({ numbers, values, expected, title }: {
  numbers: number[]
  values: number[]
  expected: number
  title: string
}) {
  const width = 720
  const height = 160
  const pad = { l: 8, r: 8, t: 10, b: 22 }
  const max = Math.max(expected * 1.15, ...values)
  const bw = (width - pad.l - pad.r) / numbers.length
  const y = (v: number) => pad.t + (1 - v / max) * (height - pad.t - pad.b)
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        {numbers.map((n, i) => {
          const v = values[i]
          return (
            <g key={n}>
              <rect x={pad.l + i * bw + 1} width={Math.max(1, bw - 2)} y={y(v)} height={height - pad.b - y(v)}
                className={v >= expected ? 'bar bar-hi' : 'bar bar-lo'}>
                <title>{`${n}: ${v} (ожидается ${expected.toFixed(1)})`}</title>
              </rect>
              {numbers.length <= 50 && (
                <text x={pad.l + i * bw + bw / 2} y={height - 6} textAnchor="middle" className="tick">{n}</text>
              )}
            </g>
          )
        })}
        <line x1={pad.l} x2={width - pad.r} y1={y(expected)} y2={y(expected)} className="expected" />
      </svg>
      <figcaption className="caption">{title}</figcaption>
    </figure>
  )
}
