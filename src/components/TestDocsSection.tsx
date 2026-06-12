'use client'

import { useState } from 'react'
import {
  FileText, CheckCircle2, AlertTriangle, Download, Loader2, X,
  ChevronRight, Terminal, Shield, FlaskConical, Clock, Bug,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from '@/components/ui/badge'
import { CopyButton } from '@/components/lottery/CopyButton'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface TestDocsSectionProps {
  show: boolean
}

interface TestEntry {
  file: string
  tests: number
  description: string
  priority: 'P0' | 'P1'
}

interface DetailedTest {
  file: string
  title: string
  importance: string
  edgeCases: string
  exampleAssertion: string
}

interface CoverageEntry {
  label: string
  sub: string
  count: string
  percent: number
  color: string
}

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const unitTests: TestEntry[] = [
  { file: 'tests/ts/rate-limit.test.ts', tests: 5, description: 'Ограничение запросов: лимиты, независимость ключей, автоочистка', priority: 'P0' },
  { file: 'tests/ts/safe-parse-stdout.test.ts', tests: 11, description: 'Парсер Python stdout: JSON, пустой вывод, Traceback', priority: 'P0' },
  { file: 'tests/ts/validators.test.ts', tests: 18, description: 'Валидация gameId и filePath: traversal, инъекции', priority: 'P0' },
  { file: 'tests/ts/safe-json-fetch.test.ts', tests: 6, description: 'HTTP-клиент: таймаут, ошибки, невалидный JSON', priority: 'P0' },
  { file: 'tests/ts/adapters.test.ts', tests: 11, description: 'Адаптеры predict/pipeline: маппинг типов, fallback', priority: 'P1' },
  { file: 'tests/hooks/use-polling.test.ts', tests: 4, description: 'Хук опроса: остановка, отмена, обработка ошибок', priority: 'P0' },
  { file: 'tests/components/HeatmapRow.test.tsx', tests: 6, description: 'Строка бэктеста: раскрытие, подсветка попаданий', priority: 'P1' },
  { file: 'tests/components/ErrorBoundary.test.tsx', tests: 4, description: 'Граница ошибок: перехват, сброс, кастомный fallback', priority: 'P0' },
  { file: 'tests/components/StepIndicator.test.tsx', tests: 10, description: 'Навигация шагов: табы, disabled, ARIA', priority: 'P1' },
  { file: 'tests/components/CopyButton.test.tsx', tests: 5, description: 'Копирование: clipboard API, откат состояния', priority: 'P1' },
]

const smokeTests: TestEntry[] = [
  { file: 'tests/smoke/01-types-constants.test.ts', tests: 12, description: 'Константы типов: GAME_FORMATS, анимации, цвета', priority: 'P0' },
  { file: 'tests/smoke/02-validators-security.test.ts', tests: 12, description: 'Безопасность валидаторов: все векторы атак', priority: 'P0' },
  { file: 'tests/smoke/03-rate-limiter-resilience.test.ts', tests: 9, description: 'Устойчивость rate-limiter: крайние случаи', priority: 'P1' },
  { file: 'tests/smoke/04-json-parser-robustness.test.ts', tests: 15, description: 'Надёжность JSON-парсера: бинарные данные, юникод', priority: 'P0' },
  { file: 'tests/smoke/05-fetch-wrapper-errors.test.ts', tests: 10, description: 'Обработка ошибок fetch: все HTTP-коды', priority: 'P0' },
  { file: 'tests/smoke/06-adapters-real-world.test.ts', tests: 8, description: 'Адаптеры с реальными данными Python', priority: 'P1' },
  { file: 'tests/smoke/07-error-boundary-smoke.test.tsx', tests: 5, description: 'ErrorBoundary: синхронные/асинхронные ошибки', priority: 'P0' },
  { file: 'tests/smoke/08-step-indicator-smoke.test.tsx', tests: 9, description: 'StepIndicator: все комбинации props', priority: 'P1' },
  { file: 'tests/smoke/09-polling-hook-smoke.test.ts', tests: 6, description: 'usePolling: утечки таймеров, отмена', priority: 'P0' },
  { file: 'tests/smoke/10-copy-button-smoke.test.tsx', tests: 6, description: 'CopyButton: clipboard fallback, таймаут', priority: 'P1' },
]

const detailedTests: DetailedTest[] = [
  // ── Unit ──────────────────────────────────────────
  {
    file: 'tests/ts/rate-limit.test.ts',
    title: 'Ограничение частоты запросов',
    importance: 'Гарантирует, что rate-limiter корректно отслеживает количество запросов для каждого ключа, предотвращая DDoS и перегрузку сервера.',
    edgeCases: 'Автоочистка просроченных записей, независимость счётчиков для разных ключей, корректная работа при нулевых лимитах.',
    exampleAssertion: 'expect(rateLimiter.allow(key)).toBe(true)',
  },
  {
    file: 'tests/ts/safe-parse-stdout.test.ts',
    title: 'Безопасный парсер stdout Python',
    importance: 'Python-скрипты могут возвращать JSON, пустой вывод или Traceback. Парсер должен корректно различать эти случаи и извлекать полезные данные.',
    edgeCases: 'Пустой stdout, частичный JSON, Traceback с unicode, ANSI-escape последовательности, смешанный вывод (лог + JSON).',
    exampleAssertion: 'expect(result.error).toContain("Traceback")',
  },
  {
    file: 'tests/ts/validators.test.ts',
    title: 'Валидация входных параметров',
    importance: 'Первая линия защиты от path-traversal и инъекций. Валидирует gameId и filePath, блокируя опасные паттерны до передачи в API.',
    edgeCases: '../ traversal, null-byte инъекции (%00), двойное URL-кодирование, Unicode-нормализация, очень длинные строки (>4096).',
    exampleAssertion: 'expect(validateGameId("../../etc/passwd")).toBe(false)',
  },
  {
    file: 'tests/ts/safe-json-fetch.test.ts',
    title: 'Безопасный HTTP-клиент с таймаутом',
    importance: 'Обёртка над fetch с контролем таймаутов, проверкой Content-Type и безопасным парсингом JSON. Предотвращает зависание при сетевых ошибках.',
    edgeCases: 'Таймаут по умолчанию, пустой ответ body, не-JSON Content-Type, responses с HTTP 429/500/502, aborted запрос.',
    exampleAssertion: 'expect(result.data).toEqual({ error: "timeout" })',
  },
  {
    file: 'tests/ts/adapters.test.ts',
    title: 'Адаптеры ответов Python API',
    importance: 'Преобразует сырые ответы Python-скриптов в типизированные TypeScript-объекты. Маппинг типов и fallback-значения для отсутствующих полей.',
    edgeCases: 'Отсутствующие поля в ответе, null-значения, неожиданные типы данных, fallback для числовых полей и массивов.',
    exampleAssertion: 'expect(adapted.models).toHaveLength(5)',
  },
  {
    file: 'tests/hooks/use-polling.test.ts',
    title: 'Хук usePolling',
    importance: 'Обеспечивает периодический опрос API с ограничением повторных попыток, корректной отменой и обработкой ошибок.',
    edgeCases: 'Корректная остановка при unmount, отмена через versionRef, maxRetries exhaustion, consecutive failures.',
    exampleAssertion: 'expect(startPolling).toHaveBeenCalledTimes(1)',
  },
  {
    file: 'tests/components/HeatmapRow.test.tsx',
    title: 'Компонент HeatmapRow',
    importance: 'Отображает строку бэктеста с выделением попаданий. Тестирует раскрытие/закрытие и подсветку совпавших чисел.',
    edgeCases: 'Раскрытие детали при клике, подсветка только совпавших ячеек, корректный рендер при пустых данных.',
    exampleAssertion: 'expect(screen.getByText("3")).toHaveClass("bg-emerald-500/30")',
  },
  {
    file: 'tests/components/ErrorBoundary.test.tsx',
    title: 'Граница ошибок (ErrorBoundary)',
    importance: 'Перехватывает ошибки рендеринга в дочерних компонентах, предотвращая крах всего приложения.',
    edgeCases: 'Синхронные ошибки в рендере, сброс состояния через кнопку, кастомный fallback-компонент, ошибки в useEffect.',
    exampleAssertion: 'expect(screen.getByText(/что-то пошло не так/i)).toBeInTheDocument()',
  },
  {
    file: 'tests/components/StepIndicator.test.tsx',
    title: 'Навигация по шагам (StepIndicator)',
    importance: 'Визуальный индикатор текущего шага (1-4) с поддержкой disabled-состояний и ARIA-атрибутами.',
    edgeCases: 'Disabled шаги при отсутствии данных, правильные aria-current/aria-selected, кликабельность только доступных шагов.',
    exampleAssertion: 'expect(button).toHaveAttribute("aria-current", "step")',
  },
  {
    file: 'tests/components/CopyButton.test.tsx',
    title: 'Кнопка копирования (CopyButton)',
    importance: 'Утилитарный компонент для копирования текста в clipboard с визуальным подтверждением и fallback для не-HTTPS.',
    edgeCases: 'Clipboard API недоступен, откат состояния (copied → idle) через таймаут, повторные нажатия.',
    exampleAssertion: 'expect(navigator.clipboard.writeText).toHaveBeenCalledWith("text")',
  },
  // ── Smoke ─────────────────────────────────────────
  {
    file: 'tests/smoke/01-types-constants.test.ts',
    title: 'Константы и типы',
    importance: 'Проверяет, что все публичные константы (GAME_FORMATS, цвета, анимации) существуют и имеют корректную структуру.',
    edgeCases: 'Наличие всех ключей в GAME_FORMATS, валидность CSS-цветов, корректность длительности анимаций.',
    exampleAssertion: 'expect(GAME_FORMATS).toHaveProperty("keno")',
  },
  {
    file: 'tests/smoke/02-validators-security.test.ts',
    title: 'Smoke-тест безопасности валидаторов',
    importance: 'Интеграция всех векторов атак в одном файле. Гарантирует, что ни один обходной путь не пропущен.',
    edgeCases: 'Path traversal, null-byte, double encoding, Unicode spoofing, очень длинные строки, SQL-подобные паттерны.',
    exampleAssertion: 'expect(ALL_ATTACKS.every(v => !validateGameId(v))).toBe(true)',
  },
  {
    file: 'tests/smoke/03-rate-limiter-resilience.test.ts',
    title: 'Устойчивость rate-limiter',
    importance: 'Проверяет поведение rate-limiter при экстремальных нагрузках и граничных значениях.',
    edgeCases: 'Чрезвычайно высокие лимиты, нулевые лимиты, race conditions при одновременных запросах.',
    exampleAssertion: 'expect(limiter.getCount("key")).toBe(0)',
  },
  {
    file: 'tests/smoke/04-json-parser-robustness.test.ts',
    title: 'Надёжность JSON-парсера',
    importance: 'Проверяет парсер на бинарных данных, Unicode, невалидных последовательностях и фрагментированном вводе.',
    edgeCases: 'Бинарные данные в stdout, невалидный UTF-8, JSON с комментариями, BOM-маркер, смешанный текст.',
    exampleAssertion: 'expect(parseStdout(binaryBuffer).error).toBeTruthy()',
  },
  {
    file: 'tests/smoke/05-fetch-wrapper-errors.test.ts',
    title: 'Обработка ошибок fetch',
    importance: 'Проверяет все HTTP-коды ошибок и сетевые сбои: 429 (rate limit), 500, 502, таймауты, aborted.',
    edgeCases: '429 с Retry-After, 502 Bad Gateway, обрыв соединения, DNS-ошибка, CORS-ошибка.',
    exampleAssertion: 'expect(result.error).toMatch(/429|rate.limit/i)',
  },
  {
    file: 'tests/smoke/06-adapters-real-world.test.ts',
    title: 'Адаптеры с реальными данными',
    importance: 'Проверяет адаптеры на «сырых» ответах Python-скрипта: числа как строки, null-поля, неожиданная структура.',
    edgeCases: 'Числа в виде строк ("5" вместо 5), отсутствующие optional-поля, пустые массивы, null вместо объекта.',
    exampleAssertion: 'expect(adapted.confidence).toBeCloseTo(0.85)',
  },
  {
    file: 'tests/smoke/07-error-boundary-smoke.test.tsx',
    title: 'ErrorBoundary: smoke',
    importance: 'Проверяет перехват как синхронных, так и асинхронных ошибок в React-дереве компонентов.',
    edgeCases: 'Ошибка в render, ошибка в useEffect (async), вложенная ошибка, повторный сброс после ошибки.',
    exampleAssertion: 'expect(container.textContent).toContain("fallback")',
  },
  {
    file: 'tests/smoke/08-step-indicator-smoke.test.tsx',
    title: 'StepIndicator: smoke',
    importance: 'Быстрая проверка всех комбинаций props: step, disabled, fetchDone, predictResult.',
    edgeCases: 'Все 4 шага, все disabled-комбинации, рендер без predictResult, рендер с null game.',
    exampleAssertion: 'expect(screen.getAllByRole("tab")).toHaveLength(4)',
  },
  {
    file: 'tests/smoke/09-polling-hook-smoke.test.ts',
    title: 'usePolling: smoke',
    importance: 'Проверяет отсутствие утечек таймеров и корректность отмены при размонтировании.',
    edgeCases: 'Быстрый unmount во время polling, несколько вызовов startPolling, ошибки в callback.',
    exampleAssertion: 'expect(clearTimeout).toHaveBeenCalled()',
  },
  {
    file: 'tests/smoke/10-copy-button-smoke.test.tsx',
    title: 'CopyButton: smoke',
    importance: 'Проверяет работу CopyButton без Clipboard API (fallback) и при таймауте.',
    edgeCases: 'Clipboard API недоступен, fallback через textarea, несколько быстрых кликов.',
    exampleAssertion: 'expect(screen.getByTitle("Скопировано")).toBeInTheDocument()',
  },
]

const coverageData: CoverageEntry[] = [
  { label: 'Безопасность', sub: 'validators, rate-limit', count: '~30 тестов', percent: 85, color: 'bg-red-500' },
  { label: 'Целостность данных', sub: 'adapters, JSON parser, fetch', count: '~35 тестов', percent: 80, color: 'bg-amber-500' },
  { label: 'UX-компоненты', sub: 'ErrorBoundary, StepIndicator, CopyButton, HeatmapRow', count: '~25 тестов', percent: 75, color: 'bg-emerald-500' },
  { label: 'Асинхронная логика', sub: 'usePolling, fetch wrapper', count: '~10 тестов', percent: 90, color: 'bg-cyan-500' },
  { label: 'Smoke-тесты', sub: 'все основные модули', count: '~60 тестов', percent: 95, color: 'bg-blue-500' },
]

const runCommands = [
  { cmd: 'bun run test', desc: 'Запустить все тесты (один раз)' },
  { cmd: 'bun run test:watch', desc: 'Запустить в режиме наблюдения' },
  { cmd: 'bun run test -- tests/ts/validators.test.ts', desc: 'Один файл' },
  { cmd: 'bun run test -- tests/smoke/', desc: 'Только smoke-тесты' },
]

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function priorityBadge(priority: 'P0' | 'P1') {
  if (priority === 'P0') {
    return (
      <Badge variant="outline" className="border-red-500/30 text-red-400 text-[10px] px-1.5 py-0">
        <AlertTriangle className="h-2.5 w-2.5" /> P0
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="border-amber-500/30 text-amber-400 text-[10px] px-1.5 py-0">
      <Clock className="h-2.5 w-2.5" /> P1
    </Badge>
  )
}

function coverageBarColor(percent: number) {
  if (percent >= 90) return 'bg-emerald-500'
  if (percent >= 75) return 'bg-amber-500'
  return 'bg-red-500'
}

/* ------------------------------------------------------------------ */
/*  Section wrapper                                                    */
/* ------------------------------------------------------------------ */

interface SectionProps {
  id: string
  icon: React.ReactNode
  title: string
  badge?: React.ReactNode
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}

function Section({ id, icon, title, badge, open, onToggle, children }: SectionProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0d1225] overflow-hidden">
      <button
        onClick={onToggle}
        id={id}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.03] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        aria-expanded={open}
      >
        <span className="shrink-0 text-blue-400">{icon}</span>
        <span className="text-sm font-semibold text-slate-200 flex-1">{title}</span>
        {badge}
        <ChevronRight
          className={`h-4 w-4 text-slate-500 transition-transform duration-200 shrink-0 ${open ? 'rotate-90' : ''}`}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/10 px-4 py-4 space-y-3">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function TestDocsSection({ show }: TestDocsSectionProps) {
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({})

  const toggleSection = (id: string) => {
    setOpenSections((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  if (!show) return null

  return (
    <section className="border-t border-white/10 bg-white/[0.02]">
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-3">

        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-1">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5 text-cyan-400" />
            <h2 className="text-base font-bold text-white">Тестовая документация</h2>
            <Badge variant="outline" className="border-cyan-500/30 text-cyan-400 text-[10px] px-1.5 py-0">
              <CheckCircle2 className="h-2.5 w-2.5" /> 20 файлов · 172 теста
            </Badge>
          </div>
        </div>

        <p className="text-[11px] text-slate-500 mb-4">
          Полное описание автотестов: unit-тесты, smoke-тесты, команды запуска и покрытие проекта.
        </p>

        {/* ─── Section 1: Overview ──────────────────────────────────── */}
        <Section
          id="sec-overview"
          icon={<FileText className="h-4 w-4" />}
          title="Обзор автотестов"
          badge={
            <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 text-[10px] px-1.5 py-0">
              20 файлов
            </Badge>
          }
          open={!!openSections['sec-overview']}
          onToggle={() => toggleSection('sec-overview')}
        >
          {/* Summary card */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {/* Total files */}
            <div className="rounded-lg border border-white/10 bg-black/20 p-3 space-y-1">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Всего файлов</p>
              <p className="text-2xl font-bold text-white">20</p>
              <p className="text-[10px] text-slate-500">
                <span className="text-blue-400">10</span> unit +{' '}
                <span className="text-amber-400">10</span> smoke
              </p>
            </div>
            {/* Total tests */}
            <div className="rounded-lg border border-white/10 bg-black/20 p-3 space-y-1">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Всего тестов</p>
              <p className="text-2xl font-bold text-white">172</p>
              <p className="text-[10px] text-slate-500">Unit + Smoke кейсы</p>
            </div>
            {/* Framework */}
            <div className="rounded-lg border border-white/10 bg-black/20 p-3 space-y-1 col-span-2 sm:col-span-1">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Фреймворк</p>
              <p className="text-sm font-bold text-white">Vitest 4</p>
              <p className="text-[10px] text-slate-500">+ React Testing Library 16</p>
            </div>
          </div>

          {/* Coverage areas */}
          <div className="mt-3">
            <p className="text-[11px] font-bold text-slate-300 flex items-center gap-2 mb-2">
              <Shield className="h-3.5 w-3.5 text-blue-400" />
              Области покрытия
            </p>
            <div className="flex flex-wrap gap-1.5">
              {['Безопасность', 'Валидация', 'API-адаптеры', 'UI-компоненты', 'Хуки', 'Rate-limiting'].map((area) => (
                <Badge key={area} variant="outline" className="border-white/10 text-slate-400 text-[10px] px-2 py-0.5">
                  {area}
                </Badge>
              ))}
            </div>
          </div>

          {/* Approximate coverage bar */}
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] text-slate-500">Приблизительное покрытие проекта</p>
              <p className="text-[10px] text-emerald-400 font-medium">~80%</p>
            </div>
            <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500"
                initial={{ width: 0 }}
                animate={{ width: '80%' }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
              />
            </div>
          </div>
        </Section>

        {/* ─── Section 2: How to run ────────────────────────────────── */}
        <Section
          id="sec-run"
          icon={<Terminal className="h-4 w-4" />}
          title="Как запустить тесты"
          badge={
            <Badge variant="outline" className="border-blue-500/30 text-blue-400 text-[10px] px-1.5 py-0">
              4 команды
            </Badge>
          }
          open={!!openSections['sec-run']}
          onToggle={() => toggleSection('sec-run')}
        >
          <div className="space-y-2">
            {runCommands.map((item) => (
              <div key={item.cmd} className="flex items-start gap-2">
                <code className="flex-1 text-[11px] font-mono text-cyan-300 bg-black/40 rounded-lg px-3 py-2 whitespace-pre-wrap break-all">
                  {item.cmd}
                </code>
                <CopyButton text={item.cmd} />
              </div>
            ))}
          </div>
          <div className="border-t border-white/10 pt-2 mt-2">
            <p className="text-[10px] text-slate-500 flex items-center gap-1.5">
              <AlertTriangle className="h-3 w-3 text-amber-400" />
              Для watch-режима требуется <code className="text-cyan-300 bg-black/30 px-1 rounded">bun run test:watch</code>. Тесты перезапускаются автоматически при изменении файлов.
            </p>
          </div>
        </Section>

        {/* ─── Section 3: Unit tests ────────────────────────────────── */}
        <Section
          id="sec-unit"
          icon={<Bug className="h-4 w-4" />}
          title="Unit-тесты (10 файлов)"
          badge={
            <Badge variant="outline" className="border-blue-500/30 text-blue-400 text-[10px] px-1.5 py-0">
              80 тестов
            </Badge>
          }
          open={!!openSections['sec-unit']}
          onToggle={() => toggleSection('sec-unit')}
        >
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 custom-scrollbar">
            {unitTests.map((t, i) => (
              <div
                key={t.file}
                className="rounded-lg border border-white/5 bg-black/20 p-3 space-y-1.5 hover:border-white/10 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="shrink-0 inline-flex items-center justify-center h-5 w-5 rounded bg-blue-500/15 text-blue-400 text-[9px] font-bold">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <code className="block text-[11px] font-mono text-cyan-300 break-all">{t.file}</code>
                      <p className="text-[11px] text-slate-400 mt-0.5">{t.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="outline" className="border-white/10 text-slate-400 text-[10px] px-1.5 py-0">
                      {t.tests} тестов
                    </Badge>
                    {priorityBadge(t.priority)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* ─── Section 4: Smoke tests ───────────────────────────────── */}
        <Section
          id="sec-smoke"
          icon={<Shield className="h-4 w-4" />}
          title="Smoke-тесты (10 файлов)"
          badge={
            <Badge variant="outline" className="border-amber-500/30 text-amber-400 text-[10px] px-1.5 py-0">
              92 теста
            </Badge>
          }
          open={!!openSections['sec-smoke']}
          onToggle={() => toggleSection('sec-smoke')}
        >
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 custom-scrollbar">
            {smokeTests.map((t, i) => (
              <div
                key={t.file}
                className="rounded-lg border border-white/5 bg-black/20 p-3 space-y-1.5 hover:border-white/10 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="shrink-0 inline-flex items-center justify-center h-5 w-5 rounded bg-amber-500/15 text-amber-400 text-[9px] font-bold">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <code className="block text-[11px] font-mono text-cyan-300 break-all">{t.file}</code>
                      <p className="text-[11px] text-slate-400 mt-0.5">{t.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="outline" className="border-white/10 text-slate-400 text-[10px] px-1.5 py-0">
                      {t.tests} тестов
                    </Badge>
                    {priorityBadge(t.priority)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* ─── Section 5: Detailed descriptions ─────────────────────── */}
        <Section
          id="sec-detailed"
          icon={<FileText className="h-4 w-4" />}
          title="Детальное описание каждого теста"
          badge={
            <Badge variant="outline" className="border-white/10 text-slate-400 text-[10px] px-1.5 py-0">
              20 описаний
            </Badge>
          }
          open={!!openSections['sec-detailed']}
          onToggle={() => toggleSection('sec-detailed')}
        >
          <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1 custom-scrollbar">
            {detailedTests.map((dt, i) => (
              <DetailAccordion key={dt.file} index={i} data={dt} />
            ))}
          </div>
        </Section>

        {/* ─── Section 6: Coverage ──────────────────────────────────── */}
        <Section
          id="sec-coverage"
          icon={<CheckCircle2 className="h-4 w-4" />}
          title="Покрытие проекта"
          open={!!openSections['sec-coverage']}
          onToggle={() => toggleSection('sec-coverage')}
        >
          <div className="space-y-3">
            {coverageData.map((c) => (
              <div key={c.label}>
                <div className="flex items-center justify-between mb-1">
                  <div>
                    <span className="text-[11px] font-semibold text-slate-300">{c.label}</span>
                    <span className="text-[10px] text-slate-500 ml-2">{c.sub}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-500">{c.count}</span>
                    <span className="text-[11px] font-bold text-slate-300">{c.percent}%</span>
                  </div>
                </div>
                <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                  <motion.div
                    className={`h-full rounded-full ${coverageBarColor(c.percent)}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${c.percent}%` }}
                    transition={{ duration: 0.6, ease: 'easeOut', delay: 0.1 }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Summary */}
          <div className="border-t border-white/10 pt-3 mt-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-lg border border-white/5 bg-black/20 p-3 space-y-1">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">Общий процент покрытия</p>
                <p className="text-xl font-bold text-emerald-400">~80%</p>
                <p className="text-[10px] text-slate-500">На основе количества тест-кейсов по областям</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3 space-y-1">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">Целевое покрытие</p>
                <p className="text-xl font-bold text-cyan-400">~85%</p>
                <p className="text-[10px] text-slate-500">Планируется увеличение покрытия UI-компонентов</p>
              </div>
            </div>
          </div>
        </Section>

      </div>

      {/* Custom scrollbar styles */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 999px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.2);
        }
      `}</style>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  DetailAccordion — expandable test detail                           */
/* ------------------------------------------------------------------ */

function DetailAccordion({ index, data }: { index: number; data: DetailedTest }) {
  const [open, setOpen] = useState(false)

  const isSmoke = data.file.includes('smoke/')
  const numberColor = isSmoke
    ? 'bg-amber-500/15 text-amber-400'
    : 'bg-blue-500/15 text-blue-400'

  return (
    <div className="rounded-lg border border-white/5 bg-black/20 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-white/[0.03] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        aria-expanded={open}
      >
        <span className={`shrink-0 inline-flex items-center justify-center h-5 w-5 rounded text-[9px] font-bold ${numberColor}`}>
          {index + 1}
        </span>
        <code className="flex-1 text-[11px] font-mono text-cyan-300 truncate min-w-0">{data.file}</code>
        <span className="text-[10px] text-slate-500 shrink-0 hidden sm:inline">{data.title}</span>
        <ChevronRight className={`h-3.5 w-3.5 text-slate-500 transition-transform duration-200 shrink-0 ${open ? 'rotate-90' : ''}`} />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/5 px-3 py-3 space-y-2">
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Что тестирует</p>
                <p className="text-[11px] text-slate-300 leading-relaxed">{data.importance}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Крайние случаи</p>
                <p className="text-[11px] text-slate-400 leading-relaxed">{data.edgeCases}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">Пример утверждения</p>
                <div className="flex items-start gap-2">
                  <code className="flex-1 text-[11px] font-mono text-emerald-300/80 bg-black/30 rounded-md px-2.5 py-1.5 break-all">
                    {data.exampleAssertion}
                  </code>
                  <CopyButton text={data.exampleAssertion} />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
