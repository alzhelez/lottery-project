'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { nf } from './format'

interface SideGame { slug: string; title: string; draws: number; activity: { active: boolean } }
interface AutoState {
  status: { started_at: string; status: string; current?: { stage: string; game: string | null } } | null
  running: boolean
}

const NAV = [
  { href: '/', label: 'Игры', icon: 'M4 5h16M4 12h16M4 19h10' },
  { href: '/odds', label: 'Шансы игр', icon: 'M5 19V9m7 10V5m7 14v-7' },
  { href: '/journal', label: 'Итоги прогнозов', icon: 'M4 17l5-5 4 4 7-8' },
  { href: '/my-tickets', label: 'Мои билеты', icon: 'M4 7h16v4a2 2 0 0 0 0 4v4H4v-4a2 2 0 0 0 0-4z' },
]

const when = (s?: string | null) => (s ? s.replace('T', ' ').slice(5, 16).replace('-', '.') : '')

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={d} />
    </svg>
  )
}

function readTheme(): 'dark' | 'light' {
  try {
    return localStorage.getItem('theme') === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

/** Каркас всех страниц: боковая панель с разделами, поиском и списком игр, состояние автозапуска. */
export function AppShell({ version, children }: { version: string; children: React.ReactNode }) {
  const path = usePathname()
  const [games, setGames] = useState<SideGame[]>([])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [showStale, setShowStale] = useState(false)
  const [auto, setAuto] = useState<AutoState | null>(null)
  const [tg, setTg] = useState<{ configured: boolean; queued?: number } | null>(null)
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')

  const loadGames = useCallback(() => {
    fetch('/api/games', { cache: 'no-store' }).then((r) => r.json()).then((d) => setGames(d.games ?? [])).catch(() => {})
  }, [])
  const loadAuto = useCallback(() => {
    fetch('/api/auto', { cache: 'no-store' }).then((r) => r.json()).then(setAuto).catch(() => {})
  }, [])

  useEffect(() => {
    setTheme(readTheme())
    loadGames()
    loadAuto()
    fetch('/api/telegram', { cache: 'no-store' }).then((r) => r.json()).then((d) => setTg(d.error ? null : d)).catch(() => {})
    const t = setInterval(() => { loadAuto(); loadGames() }, 60_000)
    return () => clearInterval(t)
  }, [loadGames, loadAuto])
  useEffect(() => { setOpen(false) }, [path])

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('theme', next) } catch { /* приватный режим — тема только на эту вкладку */ }
  }

  const q = query.trim().toLowerCase()
  const withData = useMemo(() => games.filter((g) => g.draws > 0 && (!q || g.title.toLowerCase().includes(q) || g.slug.includes(q)))
    .sort((a, b) => a.title.localeCompare(b.title, 'ru')), [games, q])
  const active = withData.filter((g) => g.activity.active)
  const stale = withData.filter((g) => !g.activity.active)
  const s = auto?.status
  const state = auto?.running ? 'run' : !s ? '' : s.status === 'done' ? 'ok' : s.status === 'error' ? 'bad' : ''

  const gameLink = (g: SideGame) => (
    <Link key={g.slug} href={`/games/${g.slug}`} className={`side-game ${g.activity.active ? '' : 'stale'}`}
      aria-current={path === `/games/${g.slug}` ? 'page' : undefined} data-testid={`side-${g.slug}`}>
      <span className="dot" aria-hidden />
      <span>{g.title}</span>
      <span className="count">{nf.format(g.draws)}</span>
    </Link>
  )

  return (
    <div className="shell">
      <div className="mobile-bar">
        <button className="menu-btn" onClick={() => setOpen(true)} aria-label="Открыть меню" aria-expanded={open}>
          <Icon d="M4 7h16M4 12h16M4 17h16" />
        </button>
        <Link href="/" className="brand"><span className="brand-ball" aria-hidden>7</span>Лотерейный анализатор</Link>
      </div>
      <div className={`scrim ${open ? 'open' : ''}`} onClick={() => setOpen(false)} aria-hidden />
      <aside className={`side ${open ? 'open' : ''}`} data-testid="sidebar" aria-label="Разделы и игры">
        <div className="side-head">
          <Link href="/" className="brand"><span className="brand-ball" aria-hidden>7</span>Лотерейный<br />анализатор</Link>
          <button className="side-close" onClick={() => setOpen(false)} aria-label="Закрыть меню">×</button>
        </div>
        <nav className="side-nav" aria-label="Разделы">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} aria-current={path === n.href ? 'page' : undefined}>
              <Icon d={n.icon} />{n.label}
            </Link>
          ))}
        </nav>
        <div className="side-search">
          <input type="search" placeholder="Найти игру" value={query} onChange={(e) => setQuery(e.target.value)}
            aria-label="Найти игру" data-testid="side-search" />
        </div>
        <div className="side-games" data-testid="side-games">
          <div className="side-group"><span>Игры</span><span>тиражей</span></div>
          {active.map(gameLink)}
          {!withData.length && <p className="small muted" style={{ padding: '0 .5rem' }}>{games.length ? 'Ничего не найдено' : 'Тиражи ещё не загружены'}</p>}
          {stale.length > 0 && (
            <>
              <div className="side-group">
                <button onClick={() => setShowStale((v) => !v)} aria-expanded={showStale || !!q}>
                  {showStale || q ? '▾' : '▸'} Устаревшие ({stale.length})
                </button>
              </div>
              {(showStale || q) && stale.map(gameLink)}
            </>
          )}
        </div>
        <div className="side-foot" data-testid="side-status">
          <div className="side-status">
            <span className={`pulse ${state}`} aria-hidden />
            <span>
              Автозапуск: {auto?.running
                ? <>идёт{s?.current ? ` — ${s.current.stage}` : ''}</>
                : !s ? 'ещё не запускался'
                  : s.status === 'done' ? `готово ${when(s.started_at)}`
                    : s.status === 'error' ? `ошибка ${when(s.started_at)}` : `прерван ${when(s.started_at)}`}
            </span>
          </div>
          <div className="side-status">
            <span className={`pulse ${tg?.configured ? (tg.queued ? 'bad' : 'ok') : ''}`} aria-hidden />
            <span>Telegram: {tg == null ? '…' : tg.configured ? (tg.queued ? `${tg.queued} сообщ. ждут отправки` : 'включён') : 'не настроен'}</span>
          </div>
          <div className="side-row">
            <span>v{version.split('_')[0]}</span>
            <button className="theme-btn" onClick={toggleTheme} data-testid="theme-toggle">
              {theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
            </button>
          </div>
        </div>
      </aside>
      <div className="content">{children}</div>
    </div>
  )
}
