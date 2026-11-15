interface Props {
  numbers: number[]
  hits?: number[]           // числа, которые совпали с тиражом
  marked?: number[]         // числа с обводкой: общие для всех методов (в «Обзоре»)
  tone?: 'predict' | 'actual' | 'plain' | 'cold'
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

/** Числа в виде лотерейных шаров. Совпавшие с тиражом — зелёные. */
export function Balls({ numbers, hits, marked, tone = 'predict', size = 'md', label }: Props) {
  const hitSet = new Set(hits ?? [])
  const markSet = new Set(marked ?? [])
  return (
    <span className={`balls balls-${size}`} aria-label={label ?? numbers.join(', ')}>
      {numbers.map((n, i) => (
        <span key={`${n}-${i}`} className={`ball ball-${hitSet.has(n) ? 'hit' : tone}${markSet.has(n) ? ' ball-common' : ''}`}
          {...(markSet.has(n) ? { 'data-common': '1', title: 'это число есть в прогнозе каждого метода' } : {})}>{n}</span>
      ))}
    </span>
  )
}

/** Несколько полей тиража подряд с разделителем. */
export function BlockBalls({ blocks, actual, marked, tone, size }: {
  blocks: number[][]
  actual?: number[][]
  marked?: number[][]
  tone?: Props['tone']
  size?: Props['size']
}) {
  return (
    <span className="block-balls">
      {blocks.map((b, i) => (
        <span key={i} className="block-balls-item">
          {i > 0 && <span className="block-sep" aria-hidden>|</span>}
          <Balls numbers={b} hits={actual ? b.filter((n) => actual[i]?.includes(n)) : undefined} marked={marked?.[i]} tone={tone} size={size} />
        </span>
      ))}
    </span>
  )
}
