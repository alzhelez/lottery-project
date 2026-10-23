import type { Metadata } from 'next'
import Link from 'next/link'
import { APP_VERSION } from '@/lib/version'
import './globals.css'

export const metadata: Metadata = {
  title: 'Лотерейный анализатор',
  description: 'Анализ тиражей Столото: тесты случайности и честная проверка методов прогноза',
  icons: { icon: '/favicon.svg' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&display=swap" />
      </head>
      <body>
        <header className="topbar">
          <Link href="/" className="brand"><span className="brand-ball" aria-hidden>7</span>Лотерейный анализатор</Link>
          <nav className="topnav">
            <Link href="/">Игры</Link>
            <Link href="/odds">Шансы игр</Link>
            <Link href="/journal">Итоги прогнозов</Link>
            <span className="version">версия {APP_VERSION}</span>
          </nav>
        </header>
        {children}
      </body>
    </html>
  )
}
