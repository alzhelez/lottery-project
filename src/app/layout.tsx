import type { Metadata } from 'next'
import { AppShell } from '@/components/AppShell'
import { APP_VERSION } from '@/lib/version'
import './globals.css'

export const metadata: Metadata = {
  title: 'Лотерейный анализатор',
  description: 'Анализ тиражей Столото: тесты случайности и честная проверка методов прогноза',
  icons: { icon: '/favicon.svg' },
}

// тема — до первой отрисовки, чтобы страница не мигала светлой/тёмной
const THEME = "try{if(localStorage.getItem('theme')==='light')document.documentElement.dataset.theme='light'}catch(e){}"

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&family=Unbounded:wght@500;600&display=swap" />
      </head>
      <body>
        <AppShell version={APP_VERSION}>{children}</AppShell>
      </body>
    </html>
  )
}
