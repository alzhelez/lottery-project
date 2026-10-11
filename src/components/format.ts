export const nf = new Intl.NumberFormat('ru-RU')

export function num(v: number | null | undefined, digits = 3): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function pct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : ''}${v.toLocaleString('ru-RU', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`
}

export function pval(p: number | null | undefined): string {
  if (p == null || !Number.isFinite(p)) return '—'
  if (p < 0.001) return '< 0,001'
  return p.toLocaleString('ru-RU', { maximumFractionDigits: 3 })
}

function parseRuDate(s: string): Date | null {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})/.exec(s)
  return m ? new Date(+m[3], +m[2] - 1, +m[1]) : null
}

export function plural(n: number, one: string, few: string, many: string): string {
  const a = Math.abs(n) % 100
  const b = a % 10
  if (a > 10 && a < 20) return many
  if (b > 1 && b < 5) return few
  if (b === 1) return one
  return many
}

/** «2 года 5 месяцев» между двумя датами ДД.ММ.ГГГГ. */
export function span(from: string, to: string): string {
  const a = parseRuDate(from)
  const b = parseRuDate(to)
  if (!a || !b) return ''
  let months = (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth())
  if (b.getDate() < a.getDate()) months -= 1
  if (months < 1) {
    const days = Math.max(1, Math.round((b.getTime() - a.getTime()) / 86_400_000))
    return `${days} ${plural(days, 'день', 'дня', 'дней')}`
  }
  const y = Math.floor(months / 12)
  const m = months % 12
  const parts = []
  if (y) parts.push(`${y} ${plural(y, 'год', 'года', 'лет')}`)
  if (m) parts.push(`${m} ${plural(m, 'месяц', 'месяца', 'месяцев')}`)
  return parts.join(' ')
}

export function duration(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = s % 60
  if (h) return `${h} ч ${m} мин`
  if (m) return `${m} мин ${r} с`
  return `${r} с`
}

export function dateOnly(s: string | undefined | null): string {
  return s ? s.split(' ')[0] : '—'
}
