interface Props {
  numbers: number[]
  hits?: number[]           // числа, которые совпали с тиражом
  tone?: 'predict' | 'actual' | 'plain' | 'cold'
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

/** Числа в виде лотерейных шаров. Совпавшие с тиражом — зелёные. */
export function Balls({ numbers, hits, tone = 'predict', size = 'md', label }: Props) {
  const hitSet = new Set(hits ?? [])
  return (
    <span className={`balls balls-${size}`} aria-label={label ?? numbers.join(', ')}>
      {numbers.map((n, i) => (
        <span key={`${n}-${i}`} className={`ball ball-${hitSet.has(n) ? 'hit' : tone}`}>{n}</span>
      ))}
    </span>
  )
}

/** Несколько полей тиража подряд с разделителем. */
export function BlockBalls({ blocks, actual, tone, size }: {
  blocks: number[][]
  actual?: number[][]
  tone?: Props['tone']
  size?: Props['size']
}) {
  return (
    <span className="block-balls">
      {blocks.map((b, i) => (
        <span key={i} className="block-balls-item">
          {i > 0 && <span className="block-sep" aria-hidden>|</span>}
          <Balls numbers={b} hits={actual ? b.filter((n) => actual[i]?.includes(n)) : undefined} tone={tone} size={size} />
        </span>
      ))}
    </span>
  )
}
