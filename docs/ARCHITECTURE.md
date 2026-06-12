# Локальный предсказатель — Полная архитектурная документация

**Версия 30.0** | Next.js 16 + Python 3 | 133 ML-модели | 38 игр stoloto.ru

---

## Содержание

1. [Обзор проекта](#1-обзор-проекта)
2. [Архитектура системы](#2-архитектура-системы)
3. [Структура проекта](#3-структура-проекта)
4. [Технологический стек](#4-технологический-стек)
5. [Фронтенд](#5-фронтенд)
6. [API-маршруты](#6-api-маршруты)
7. [Python-движок ML](#7-python-движок-ml)
8. [Инфраструктура](#8-инфраструктура)
9. [База данных](#9-база-данных)
10. [Безопасность](#10-безопасность)
11. [UX/UI](#11-uxui)
12. [Кэширование](#12-кэширование)
13. [Зависимости](#13-зависимости)

---

## 1. Обзор проекта

### 1.1. Описание

«Локальный предсказатель» — это full-stack гибридное приложение для анализа и прогнозирования лотерейных тиражей с сайта [stoloto.ru](https://www.stoloto.ru). Система анализирует **38 активных лотерейных игр**, используя ансамбль из **133 ML-моделей**, и представляет результаты через 4-шаговый wizard-интерфейс.

### 1.2. Ключевые возможности

| Возможность | Описание |
|---|---|
| **Анализ 38 игр** | Автоматическое сканирование всех активных игр на stoloto.ru: chi-squared, автокорреляция, горячие/холодные числа |
| **Загрузка тиражей** | Скачивание полной истории тиражей для выбранной игры с валидацией данных |
| **Прогноз (133 модели)** | Ансамбль ML-моделей: частотные, gap-анализ, марковские цепи, Монте-Карло, байесовские и др. |
| **Pipeline** | Позиционный ансамбль: голосование моделей по позициям, частотный анализ, top-3 модели |
| **Бэктест и CV** | Историческая точность, k-fold кросс-валидация, симуляция 5000 итераций Монте-Карло |
| **Автоматический pipeline** | После прогноза автоматически запускается позиционный анализ (шаг 4) |

### 1.3. Почему гибрид Next.js + Python?

Python-часть (133 ML-модели) изначально была написана как **Streamlit-приложение** (`lp_v130_app.py`). Миграция на Next.js потребовала «мокирования» Streamlit-модуля для переиспользования движка в CLI-контексте. Это позволяет:

- Сохранить годы разработки ML-движка без переписывания
- Использовать современные веб-технологии (React 19, TypeScript 5, Tailwind CSS 4) для UI
- Запускать тяжёлые вычисления вне процесса Node.js
- Обеспечить отзывчивый UI через фоновое выполнение + polling

---

## 2. Архитектура системы

### 2.1. Высокоуровневая схема

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ПОЛЬЗОВАТЕЛЬ (браузер)                            │
│                          Caddy (порт 81)                                 │
│                     read_timeout: 900s / write_timeout: 900s            │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ reverse_proxy → localhost:3000
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     NEXT.JS 16 (App Router, порт 3000)                   │
│                         Runtime: Bun                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────────┐    │
│  │  React 19 SPA   │  │  API Routes     │  │  In-memory Cache       │    │
│  │  (page.tsx)     │  │  (5 endpoints)  │  │  (30min TTL)           │    │
│  │                 │  │                 │  │  rate-limit (500 max)  │    │
│  │  4-step wizard  │  │  cache-first    │  │  draw counts (5min)    │    │
│  │  polling (5s)   │  │  background     │  │                        │    │
│  │  sessionStorage │  │  execution      │  │                        │    │
│  └────────┬────────┘  └────────┬────────┘  └────────────────────────┘    │
│           │ POST JSON         │ child_process.spawn                       │
│           │                   ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                    PYTHON 3.10+                                    │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │   │
│  │  │analyze.py│ │predict.py│ │pipeline.py│ │fetch_draws.py       │ │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────────┬───────────┘ │   │
│  │       │            │            │                  │             │   │
│  │  ┌────▼────────┐ ┌─▼─────────┐ ┌─▼──────────┐ ┌────▼──────────┐  │   │
│  │  │stoloto      │ │lp_v130    │ │lottery     │ │stoloto.ru     │  │   │
│  │  │analyzer_v3  │ │_app.py    │ │_pipeline   │ │API            │  │   │
│  │  │.py          │ │(133 modeli)│ │.py         │ │               │  │   │
│  │  └─────────────┘ └───────────┘ └────────────┘ └───────────────┘  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────┐  ┌──────────────────────────────────────────────┐  │
│  │ Prisma / SQLite  │  │  Файловая система                           │  │
│  │ GameAnalysis     │  │  data/draws/draws_{game}.txt (персистентн.) │  │
│  │ PredictionLog    │  │  python/stoloto_analysis_v3.json (кэш 7д)   │  │
│  │                  │  │  /tmp/model_report_{game}.json               │  │
│  └─────────────────┘  │  /tmp/pipeline_data_{game}.json               │  │
│                       └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2. Поток данных через wizard

```
 Шаг 1: АНАЛИЗ                              Шаг 2: ТИРАЖИ
 ┌──────────┐    ┌──────────────┐            ┌──────────┐    ┌──────────────┐
 │ POST     │───▶│ analyze.py   │            │ POST     │───▶│ fetch.py     │
 │ /api/    │    │ --list-only  │            │ /api/    │    │ fetch_draws  │
 │ lottery/ │    │ stoloto      │            │ lottery/ │    │ .py          │
 │ analyze  │    │ _analyzer_v3 │            │ fetch-   │    │              │
 └──────────┘    └──────┬───────┘            │ draws    │    └──────┬───────┘
                        │                    └──────────┘           │
                        ▼                                           ▼
                 38 игр с категориями                    data/draws/draws_{game}.txt
                 (high/moderate/normal)                   (персистентный файл)
                        │                                           │
                        └───────── пользователь ────────────────────┘
                                  выбирает игру + нажимает
                                  «Загрузить все тиражи»
                                                      │
                                                      ▼
 Шаг 3: ПРОГНОЗ                             Шаг 4: PIPELINE
 ┌──────────┐    ┌──────────────┐           ┌──────────┐    ┌──────────────┐
 │ POST     │───▶│ predict.py   │           │ POST     │───▶│ pipeline.py  │
 │ /api/    │    │ lp_v130_app  │  автомат. │ /api/    │    │ lottery      │
 │ lottery/ │    │ .py (133 m.) │─────────▶│ lottery/ │    │ _pipeline    │
 │ predict  │    │ DualBayesRing│           │ pipeline │    │ .py          │
 └──────────┘    └──────┬───────┘           └──────────┘    └──────┬───────┘
                        │                                          │
                        ▼                                          ▼
                 prediction, accuracy,               final_prediction,
                 backtest heatmap, CV,                confidence, position_details,
                 Monte Carlo, frequency              top3_models, number_spectrum,
                 analysis, pairs, gaps               block1_position, frequency
```

### 2.3. Паттерн cache-first + background + polling

Каждый ресурсоемкий эндпоинт использует единый паттерн:

1. **API-запрос** → проверка in-memory кэша → если есть свежий — вернуть мгновенно (5-50ms)
2. **Нет кэша** → запустить Python-скрипт в фоне через `child_process.spawn()`
3. **Ответ** → `status: 'pending'` + `_refreshing: true`
4. **Фронтенд** → поллинг каждые 5 секунд через `usePolling()` (максимум 60 попыток)
5. **Готово** → кэш обновлён → следующий поллинг вернёт результат

Это позволяет:
- **Никогда не блокировать HTTP-соединение** более чем на ~1 секунду
- **Избежать HTTP 502/504** от Caddy/Next.js
- **Мгновенно отдавать кэшированные** результаты при повторных запросах

---

## 3. Структура проекта

```
my-project/
├── src/
│   ├── app/
│   │   ├── page.tsx                              # Главная страница — 4-шаговый wizard (706 строк)
│   │   ├── layout.tsx                            # Корневой layout: metadata, providers, шрифты
│   │   ├── globals.css                           # Глобальные стили, Tailwind директивы, кастомный скроллбар
│   │   ├── tw-animate.css                        # Анимации для Tailwind CSS
│   │   └── api/
│   │       ├── lottery/
│   │       │   ├── analyze/route.ts              # POST: анализ 38 игр через Python
│   │       │   ├── fetch-draws/route.ts          # POST: загрузка тиражей с stoloto.ru
│   │       │   ├── predict/route.ts              # POST: запуск 133 ML-моделей
│   │       │   └── pipeline/route.ts             # POST: позиционный ансамбль
│   │       └── download-project/route.ts         # GET: создание .tar.gz архива проекта
│   │
│   ├── components/
│   │   ├── lottery/
│   │   │   ├── types.ts                          # TypeScript типы: GameAnalysis, PredictionResult, PipelineResult и др.
│   │   │   ├── StepIndicator.tsx                 # Индикатор текущего шага wizard (1-4)
│   │   │   ├── Step1Analysis.tsx                 # Карточки 38 игр с категориями (high/moderate/normal/insufficient)
│   │   │   ├── Step2Draws.tsx                    # Загрузка тиражей: прогресс, количество, ссылка на stoloto.ru
│   │   │   ├── Step3Predict.tsx                  # Прогноз: блоки, бэктест, heatmap, Монте-Карло, CV, пары, gap-анализ
│   │   │   ├── Step4Pipeline.tsx                 # Pipeline: позиционный анализ, частоты, top-3 модели, сравнение
│   │   │   ├── HeatmapRow.tsx                    # Разворачиваемая строка тепловой карты бэктеста
│   │   │   └── CopyButton.tsx                    # Кнопка копирования текста в буфер обмена
│   │   ├── ui/                                   # ~40 компонентов shadcn/ui (button, card, badge, dialog, и др.)
│   │   └── ErrorBoundary.tsx                     # Глобальный обработчик ошибок React
│   │
│   ├── hooks/
│   │   ├── usePolling.ts                         # Универсальный хук поллинга с версией для отмены
│   │   ├── usePrefersReducedMotion.ts            # Доступность: определяет prefers-reduced-motion
│   │   ├── use-mobile.ts                         # Адаптив: детекция мобильного устройства через media query
│   │   └── use-toast.ts                          # Хук для toast-уведомлений (legacy, используется sonner)
│   │
│   └── lib/
│       ├── background-cache.ts                   # Общий обработчик кэша для predict/pipeline: cache-first + background
│       ├── api-utils.ts                          # DATA_DIR, safeParseStdout, validateGameId, validateFilePath, KNOWN_GAMES
│       ├── python-runner.ts                      # Кроссплатформенный поиск Python + runPythonScript (spawn)
│       ├── adapters.ts                           # Типобезопасные адаптеры: Python JSON → TypeScript (adaptPredictResult, adaptPipelineResult)
│       ├── fetch.ts                              # safeJsonFetch: таймаут, HTML-детекция, Content-Type проверка
│       ├── rate-limit.ts                         # In-memory rate limiter с автоочисткой (MAX_ENTRIES=500)
│       ├── db.ts                                 # Prisma-клиент: экземпляр для доступа к SQLite
│       └── utils.ts                              # Утилиты: cn() для слияния классов и прочие
│
├── python/
│   ├── lp_v130_app.py                            # 3525 строк — Ядро ML: класс LP132 (133 модели), DualBayesRing, FreqCache, GAME_FORMAT_HINTS
│   ├── predict.py                                # 1494 строки — CLI-обёртка: мок Streamlit, run_training, бэктест, CV, Монте-Карло
│   ├── lottery_pipeline.py                       # 1071 строка — Движок pipeline: позиционное голосование, частоты, confidence scoring
│   ├── fetch_draws.py                            # 935 строк — Загрузка тиражей: бинарный поиск, 5 форматов API, GAME_FORMAT_HINTS (44 игры)
│   ├── pipeline.py                               # 694 строки — CLI для pipeline: чтение model_report, частотный прогноз, top-3 модели
│   ├── stoloto_analyzer_v3.py                    # 560 строк — Статистический анализатор: chi2, автокорреляция, hot/cold, game existence
│   ├── api_wrapper.py                            # 192 строки — HTTP-обёртка для stoloto.ru: retry, rate-limit, session
│   ├── analyze.py                                # 335 строк — Анализатор 38 игр: --list-only флаг, кэш JSON (7 дней)
│   └── fetch.py                                  # 100 строк — Обёртка для fetch_draws.py (CLI интерфейс)
│
├── data/
│   ├── draws/                                    # Персистентные файлы тиражей: draws_4x20.txt, draws_6x45plus.txt и т.д.
│   ├── analysis/                                 # Временные файлы статуса анализа
│   ├── predictions/                              # Кэш предсказаний: predict_4x20.json и т.д.
│   ├── pipeline/                                 # Кэш pipeline: pipeline_4x20.json и т.д.
│   └── fetch_status/                             # Статусы загрузки тиражей
│
├── prisma/
│   └── schema.prisma                             # Схема SQLite: GameAnalysis + PredictionLog
│
├── public/
│   ├── logo.svg                                  # Логотип приложения
│   └── robots.txt                                # Инструкции для поисковых роботов
│
├── docs/
│   ├── ARCHITECTURE.md                           # Этот файл — полная архитектурная документация
│   └── TEST_PLAN.md                              # План тестирования
│
├── upload/                                       # Резервные копии Python-скриптов (fallback при отсутствии python/)
│
├── package.json                                  # Зависимости и скрипты (Bun runtime)
├── bun.lock                                      # Lockfile для Bun
├── Caddyfile                                     # Конфигурация Caddy: порт 81 → 3000, 15-min таймауты
├── next.config.ts                                # Конфигурация Next.js 16
├── tailwind.config.ts                            # Конфигурация Tailwind CSS 4
├── tsconfig.json                                 # Конфигурация TypeScript 5
├── postcss.config.mjs                            # Конфигурация PostCSS
├── eslint.config.mjs                             # Конфигурация ESLint 9
├── components.json                               # Конфигурация shadcn/ui
├── start_dev.sh                                  # Скрипт запуска dev-сервера
└── keepalive.sh                                  # Скрипт поддержки активности
```

---

## 4. Технологический стек

### 4.1. Обоснование выбора технологий

| Технология | Версия | Почему выбрана |
|---|---|---|
| **Next.js** | 16.1+ | App Router: API Routes в `src/app/api/`, SSR по требованию, встроенная оптимизация. Единый фреймворк для frontend + backend API |
| **React** | 19.0 | Последняя версия с concurrent features, React Compiler support, server components |
| **TypeScript** | 5.x | Строгая типизация всех данных, передаваемых между Python и Frontend. Адаптеры в `adapters.ts` |
| **Tailwind CSS** | 4.x | Utility-first CSS с JIT-компиляцией. Быстрая разработка, консистентный дизайн |
| **shadcn/ui** | latest | Компоненты на Radix UI: доступность (ARIA), keyboard navigation, темная тема. ~40 компонентов |
| **framer-motion** | 12.x | Анимации wizard-переходов (spring), анимированное раскрытие чисел, collapse/expand |
| **Bun** | latest | Быстрый runtime для Next.js, нативная поддержка TypeScript, быстрый package manager |
| **Python** | 3.10+ | numpy/scipy для ML, requests для HTTP. Мок Streamlit для переиспользования существующего кода |
| **numpy** | — | Векторные вычисления для частот, gap-анализа, Монте-Карло. Основа ML-движка |
| **scipy** | — | Статистические тесты: chi-squared, autocorrelation, z-score |
| **Prisma** | 6.11+ | Type-safe ORM для SQLite. Автоматическая генерация типов из schema |
| **SQLite** | — | Встроенная БД: нулевая конфигурация, файловое хранение, подходит для single-server |
| **Caddy** | latest | Reverse proxy: автоматический HTTPS, `XTransformPort` для мини-сервисов, настраиваемые таймауты |
| **sonner** | 2.x | Toast-уведомления: красивые, лёгкие, с поддержкой RTL и темной темы |

### 4.2.	Runtime

Приложение запускается под **Bun** вместо Node.js. Bun обеспечивает:

- **Быстрый старт** — cold start в разы быстрее Node.js
- **Нативный TypeScript** — не требуется отдельная компиляция
- **Быстрый package manager** — `bun install` вместо `npm install`
- **Совместимость** — полная поддержка Node.js API, включая `child_process.spawn`

Скрипты в `package.json`:
```json
{
  "dev": "next dev -p 3000",
  "build": "next build && cp -r .next/static .next/standalone/.next/ && cp -r public .next/standalone/",
  "start": "NODE_ENV=production bun .next/standalone/server.js",
  "lint": "eslint .",
  "db:push": "prisma db push",
  "db:generate": "prisma generate"
}
```

---

## 5. Фронтенд

### 5.1. Архитектура страницы (`src/app/page.tsx`)

Главная страница — это **single-page wizard** с 4 шагами. Общее состояние управляется через React `useState` с персистенцией в `sessionStorage`.

```typescript
// Общее состояние wizard
interface WizardState {
  step: 1 | 2 | 3 | 4
  selectedGame: GameAnalysis | null
  games: GameAnalysis[]
  drawData: { game: string; total_draws: number; data_file: string } | null
  prediction: PredictionResult | null
  pipeline: PipelineResult | null
  isLoading: { analysis: boolean; draws: boolean; predict: boolean; pipeline: boolean }
}
```

**Персистенция**: при каждом изменении состояния вызывается `sessionStorage.setItem('lp_state', JSON.stringify(state))`. При загрузке страницы состояние восстанавливается — пользователь не теряет прогресс при refresh.

**Навигация**:
- Клавиши ← → для переключения шагов
- Кнопки «Далее» / «Назад»
- Шаг 3 и 4 автоматически запускаются после завершения предыдущего

### 5.2. Компоненты (`src/components/lottery/`)

#### `types.ts` — Типизация

Центральный файл с TypeScript-интерфейсами для данных Python → Frontend:

```typescript
interface GameAnalysis {
  key: string
  name: string
  score: number
  verdict: string          // 'high_anomaly' | 'moderate_anomaly' | 'normal' | 'insufficient'
  verdict_color: string    // 'red' | 'amber' | 'green' | 'gray'
  draws: number
  chi2_p: number | null
  autocorr: number | null
  hot_numbers: number[]
  cold_numbers: number[]
  redirect_target: string | null
}

interface PredictionResult {
  status: string
  game_format: string       // "4x4"
  game_key: string
  total_draws: number
  prediction: {
    block1: number[]
    block2: number[]
  }
  consensus_strength: { block1: number; block2: number }
  backtest: { ... }
  monte_carlo: { iterations, expected_hits, ci_95_low, ci_95_high, p_ge_5 }
  cross_validation: { ... }
  models_used: number
  analysis_methods: string[]
  sum_range_stats: { ... } | null
  cross_game: { ... } | null
  top5_models?: { ... }
  consensusVotesB1?: Record<string, number>
  consensusVotesB2?: Record<string, number>
}

interface PipelineResult {
  status: string
  game_key: string
  game_format: string
  total_draws: number
  prediction: { block1: number[]; block2: number[] }
  confidence: { block1: number; block2: number; overall: number; consensus_strength: number }
  position_analysis: { block1: Record<string, ...>; block2: Record<string, ...> }
  block1_position?: { ... }
  block1_frequency?: { ... }
  top3_models?: { ... }
  number_spectrum?: { ... }
}
```

#### `StepIndicator.tsx` — Индикатор шагов

Горизонтальная навигация с 4 шагами. Каждый шаг отображает:
- Номер шага (цифра)
- Название шага (Анализ → Тиражи → Прогноз → Pipeline)
- Активный/завершённый/отключённый стиль
- ARIA: `role="tablist"`, `aria-selected`, `aria-controls`

#### `Step1Analysis.tsx` — Анализ игр

Отображает 38 игр, сгруппированных по категориям:
- **Высокая аномалия** (score ≥ 80): красные карточки —_games с неравномерным распределением
- **Умеренная аномалия** (score ≥ 60): amber-карточки
- **Нормальные** (score < 60, draws ≥ 50): зелёные карточки
- **Недостаточно данных** (draws < 50): серые карточки

Каждая карточка показывает: название игры, количество тиражей, score, chi2, автокорреляцию, hot/cold числа.

#### `Step2Draws.tsx` — Загрузка тиражей

После выбора игры на шаге 1:
- Автоматический запуск загрузки тиражей
- Прогресс-бар и индикатор фонового обновления
- Количество загруженных тиражей
- Внешняя ссылка на `stoloto.ru/{game}/archive`
- Кнопка «Загрузить все тиражи»

#### `Step3Predict.tsx` — Прогноз

Самый насыщенный шаг. Показывает:
- **Основной прогноз**: Block 1 и Block 2 с анимированным раскрытием чисел (framer-motion spring)
- **Сила консенсуса**: процент моделей, согласных с прогнозом
- **Бэктест**: средняя точность за 50/100/200 тиражей, улучшение vs random baseline
- **Тепловая карта** (HeatmapRow): цветовая визуализация попаданий по тиражам
- **Топ-5 моделей**: лучшие модели с их прогнозами
- **Монте-Карло**: доверительные интервалы, вероятность ≥5 попаданий
- **Кросс-валидация**: k-fold результаты
- **Частотный анализ**: частота каждого числа
- **Топ-10 пар чисел**: наиболее частые co-occurrence пары
- **Просроченные числа**: числа с наибольшим overdue_score
- **Спектр консенсуса**: голоса моделей по числам

#### `Step4Pipeline.tsx` — Позиционный ансамбль

- **Прогноз Pipeline**: Block 1 и Block 2 с confidence score
- **Позиционный анализ**: голосование моделей по каждой позиции (P0, P1, ...)
- **Top-3 модели**: 3 лучшие модели по недавней точности
- **Частотный анализ Pipeline**: recency-weighted частоты
- **Number Spectrum**: агрегированные голоса по всем позициям
- **Сравнение**: базовый прогноз vs Pipeline — зелёные (консенсус), синие (только базовый), фиолетовые (только pipeline)

#### `HeatmapRow.tsx` — Тепловая карта бэктеста

Разворачиваемая строка для каждого исторического тиража:
- Фактические числа (act_b1, act_b2)
- Предсказанные числа (pred_b1, pred_b2)
- Цветовое кодирование попаданий
- Лучший модель для данного тиража
- ARIA: `aria-expanded` для collapse/expand

#### `CopyButton.tsx` — Копирование в буфер

Компонент кнопки с иконкой-копиркой. При нажатии:
- Копирует текст в `navigator.clipboard`
- Показывает уведомление через `sonner`
- Содержит `<span className="sr-only">` для screen reader

### 5.3. State Management

Используется **React useState + sessionStorage**. Нет external state management (no Redux, no Zustand in lottery components).

```typescript
// Сохранение состояния
useEffect(() => {
  sessionStorage.setItem('lp_state', JSON.stringify({
    step, selectedGame, games, drawData, prediction, pipeline
  }))
}, [step, selectedGame, games, drawData, prediction, pipeline])

// Восстановление состояния
useEffect(() => {
  const saved = sessionStorage.getItem('lp_state')
  if (saved) setState(JSON.parse(saved))
}, [])
```

### 5.4. Обработка ошибок

- **ErrorBoundary** (`src/components/ErrorBoundary.tsx`): обёртка вокруг приложения. При uncaught error показывает fallback UI с кнопкой перезагрузки
- **safeJsonFetch** (`src/lib/fetch.ts`): проверяет `res.ok`, Content-Type, обнаруживает HTML-ответы
- **Toasts** (sonner): уведомления об ошибках и успехах для каждого шага wizard
- **API-ошибки**: каждое действие в wizard имеет отдельный обработчик ошибок с `hint` для пользователя

---

## 6. API-маршруты

Все API-маршруты расположены в `src/app/api/` и реализованы как Next.js Route Handlers.

### 6.1. `POST /api/lottery/analyze` — Анализ игр

**Файл**: `src/app/api/lottery/analyze/route.ts`

**Назначение**: Анализ всех активных игр на stoloto.ru с помощью Python.

**Запрос**: `POST /api/lottery/analyze` (body: `{}` или `{ refresh: true }`)

**7-уровневый fallback**:
1. **In-memory cache** (30 min TTL) → мгновенный возврат (~5-50ms)
2. **Python file cache** (newer than memory, 7-day TTL) → возврат + background refresh
3. **Stale in-memory** → возврат + background refresh
4. **Quick game list** (`analyze.py --list-only`, ~5-15s) → возврат + background refresh
5. **Python file cache** (любой) → возврат + background refresh
6. **Minimal hardcoded** 38 игр → возврат + background refresh
7. **Background full analysis** → обновление кэша для будущих запросов

**Кэш Python**: `python/stoloto_analysis_v3.json` с TTL = 7 дней.

**Background refresh**: полный анализ через `analyze.py` (без `--list-only`), до 30 минут.

### 6.2. `POST /api/lottery/fetch-draws` — Загрузка тиражей

**Файл**: `src/app/api/lottery/fetch-draws/route.ts`

**Запрос**: `POST /api/lottery/fetch-draws` (body: `{ game: "4x20" }`)

**Логика**:
1. Если файл `data/draws/draws_{game}.txt` существует → вернуть сразу (200, <1s)
2. Запустить фоновое обновление (fire-and-forget)
3. Если файла нет → вернуть `_refreshing: true`, запустить фоновую загрузку
4. **2-минутный cooldown** между фоновыми обновлениями для одной игры
5. **5-минутный максимальный таймаут** фоновой задачи

**Rate limit**: 5 запросов / 60 секунд на игру.

**Output**:
```json
{
  "game": "4x20",
  "total_draws": 13310,
  "data_file": "/home/z/my-project/data/draws/draws_4x20.txt",
  "_refreshing": true
}
```

### 6.3. `POST /api/lottery/predict` — Запуск ML-моделей

**Файл**: `src/app/api/lottery/predict/route.ts`

**Запрос**: `POST /api/lottery/predict` (body: `{ game: "4x20", data_file: "...", enable_cv: true }`)

**Реализация**: использует обобщённый `createCachedOperationHandler` из `background-cache.ts`:

```typescript
const handlePredict = createCachedOperationHandler({
  operationLabel: 'predict',
  scriptName: 'predict.py',
  scriptArgs: (_game, _file, extra) => {
    const args = ['--file', _file]
    if (extra?.enable_cv !== true) args.push('--no-cv')
    args.push('--batch-step', '50', '--full-every', '3')
    return args
  },
  timeoutMs: 600_000,  // 10 минут
})
```

**Кэш**: in-memory 30min TTL + ключ по `game + fileModTime`.

**Python-скрипт**: `predict.py --file /path/to/draws_4x20.txt --batch-step 50 --full-every 3`

### 6.4. `POST /api/lottery/pipeline` — Позиционный ансамбль

**Файл**: `src/app/api/lottery/pipeline/route.ts`

**Запрос**: `POST /api/lottery/pipeline` (body: `{ game: "4x20" }`)

**Реализация**: аналогично predict через `createCachedOperationHandler`:

```typescript
const handlePipeline = createCachedOperationHandler({
  operationLabel: 'pipeline',
  scriptName: 'pipeline.py',
  scriptArgs: (game) => ['--game', game],
  timeoutMs: 600_000,
})
```

**Python-скрипт**: `pipeline.py --game 4x20` — читает `/tmp/pipeline_data_{game}.json` из predict.

### 6.5. `GET /api/download-project` — Скачивание проекта

**Файл**: `src/app/api/download-project/route.ts`

**Назначение**: создаёт `.tar.gz` архив проекта для локального запуска.

**Что включается**:
- `src/`, `python/`, `prisma/`, `public/`, `next.config.ts`, `package.json`, и т.д.
- Автоматически генерируется `README.md` с инструкциями
- Автоматически генерируется `.env` с `DATABASE_URL`
- Скрипты из `upload/` копируются в `python/` как fallback

**Что исключается**: `node_modules/`, `.next/`, `.git/`, `*.db`, `__pycache__/`

---

## 7. Python-движок ML

### 7.1. Обзор Python-модулей

```
python/                           Строк      Назначение
├── lp_v130_app.py                3525       Ядро ML: 133 модели, DualBayesRing, FreqCache
├── predict.py                    1494       CLI: run_training, бэктест, CV, Монте-Карло, мок Streamlit
├── lottery_pipeline.py           1071       Движок pipeline: позиционное голосование, recency ensemble
├── fetch_draws.py                 935       Загрузка тиражей: бинарный поиск, 5 форматов API
├── pipeline.py                    694       CLI pipeline: чтение model_report, частоты, top-3
├── stoloto_analyzer_v3.py         560       Статистический анализатор: chi2, автокорреляция
├── api_wrapper.py                 192       HTTP-обёртка для stoloto.ru: retry, rate-limit
├── analyze.py                     335       CLI анализатор 38 игр: --list-only, кэш 7 дней
└── fetch.py                       100       CLI обёртка для fetch_draws.py
                                  ─────
                                  5381       Итого строк Python-кода
```

### 7.2. Класс LP132 — Ядро ML (133 модели)

**Файл**: `python/lp_v130_app.py` (3525 строк)

Класс `LP132` содержит все 133 модели предсказания. Каждая модель возвращает кортеж `(block1: int[], block2: int[])`. Модели используют **lazy evaluation** через метод `_S(key, fn)`:

```python
class LP132:
    def _S(self, key, fn):
        """Lazy evaluation с кэшем — результат вычисляется один раз."""
        if key not in self._c:
            self._c[key] = fn()
        return self._c[key]
```

#### Группы моделей

##### G1: Базовые модели (20 моделей, p1-p20)

| ID | Название | Алгоритм |
|---|---|---|
| p1 | `m01_freq` | Экспоненциально-затухающая частота, штраф за последние 3 тиража |
| p2 | `m02_markov` | Марковская цепь: P(next \| current) с весами по давности |
| p3 | `m03_gap` | Overdue-числа: чем дольше не выпадало — тем выше приоритет |
| p4 | `m04_pattern` | Поиск тиражей с ≥2 совпадениями в окне 30 |
| p5 | `m05_neural` | Квадратичные веса по свежести (w = (i/N)²) |
| p6 | `m06_monte` | 500 Монте-Карло выборок с вероятностями из частот |
| p7 | `m07_genetic` | Fitness-based: вес = совпадения с последним тиражом |
| p8 | `m08_balance` | Отклонение от ожидаемой частоты (дисбаланс) |
| p9 | `m09_deep` | Глубокие паттерны: d[i] → d[i+2] при совпадении с последним |
| p10 | `m10_fibonacci` | Индексация по числам Фибоначчи в отсортированных частотах |
| p11 | `m11_prime` | Буст простых чисел (×1.3) и штраф составных (×0.85) |
| p12 | `m12_momentum` | Импульс: разница частот последних 5 vs 10 тиражей |
| p13 | `m13_zscore` | Z-score аномалии: \|f - μ\| / σ |
| p14 | `m14_entropy` | Позиционная энтропия (нестабильность позиции числа) |
| p15 | `m15_cyclic` | Циклические паттерны: совпадение возраста с средним интервалом |
| p16 | `m16_ensemble` | Ансамбль 5 моделей (m01, m02, m03, m12, m13) |
| p17 | `m17_recency` | Recency-weighted частота (фокус на последних тиражах) |
| p18 | `m18_pairs` | Анализ парных co-occurrence чисел |
| p19 | `m19_regression_mean` | Регрессия к среднему |
| p20 | `m20_ewma(0.15)` | Экспоненциально-взвешенное скользящее среднее (α=0.15) |

##### G2: Window-варианты (12 моделей, p21-p32)

Частотный анализ с разными окнами (5, 10, 15, 20, 30, 50, 70, 100, 150, 200, 300, 500 тиражей). Метод `_window(w)`: считает частоты только в пределах последних `w` тиражей.

##### G3: Gap+Freq гибриды (13 моделей, p33-p45)

Комбинация gap-анализа и частот с разными boost-коэффициентами: 0.8, 1.0, 1.2, 1.5, 2.0, 0.5, 1.8, 2.5, 0.3, 3.0, 0.6, 1.3, 0.9. Метод `_gap_freq(b)`: combines overdue penalty + frequency.

##### G4: EWMA альфа-варианты (12 моделей, p46-p57)

Экспоненциально-взвешенное среднее с разными коэффициентами затухания: 0.05, 0.10, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.08, 0.12, 0.18. Метод `m20_ewma(a)`.

##### G5: Velocity/Z-score/Bayesian/Draw-type (13 моделей, p58-p70)

| ID | Название | Алгоритм |
|---|---|---|
| p58 | `_velocity('vel1a', 10, 20)` | Скорость изменения частоты (окна 10/20) |
| p59 | `_velocity('vel1b', 5, 15)` | Альтернативные окна для velocity |
| p60 | `_recency_z(30)` | Z-score на последних 30 тиражах |
| p61 | `_recency_z(50)` | Z-score на последних 50 тиражах |
| p62 | `_recency_z(80)` | Z-score на последних 80 тиражах |
| p63 | `_bayesian(0.3)` | Байесовская оценка с prior strength 0.3 |
| p64 | `_bayesian(0.5)` | Байесовская оценка с prior strength 0.5 |
| p65 | `_bayesian(0.8)` | Байесовская оценка с prior strength 0.8 |
| p66 | `_block_streak('bs1', 30)` | Серия одинаковых блоков за 30 тиражей |
| p67 | `_block_streak('bs2', 50)` | Серия одинаковых блоков за 50 тиражей |
| p68 | `_draw_type_freq` | Частоты, разделённые по типу тиража (STD/RNG) |
| p69 | `_cross_block_gap` | Анализ разрывов между block1 и block2 |
| p70 | `_fourier` | Фурье-анализ периодичности чисел |

##### G6: Взвешенные ансамбли (29 моделей, p71-p99)

Взвешенные комбинации 4 базовых моделей (freq, markov, gap, momentum) с разными весовыми наборами:

```
[2,1,1,1] [1,2,1,1] [1,1,2,1] [1,1,1,2]   — сильный буст одной модели
[3,1,0,0] [0,3,1,0] [1,0,3,0] [1,0,0,3]   — доминирование одной модели
[2,2,0,0] [0,2,2,0] [2,0,2,0] [2,1,1,0]   — пара доминирует
[1.5,1.5,1,0] [1,1.5,1.5,0]                — равный буст пары
[0,1,1.5,1.5] [1.5,0,1,1.5]                — остальные комбинации
[1,1,1,1] ...                                — равные веса и смешанные
```

##### G7: Уникальные модели (21 модель, p100-p120)

| ID | Название | Алгоритм |
|---|---|---|
| p100 | `_positional_drift` | Анализ смещения чисел по позициям |
| p101 | `_window(25)` | Дополнительное окно 25 тиражей |
| p102 | `_recency_z(100)` | Z-score на 100 тиражах |
| p103 | `_bayesian(0.2)` | Сильный prior (0.2) |
| p104 | `_hot_streak('hot1', 10, 3)` | Горячая серия: 10 тиражей, порог 3 |
| p105 | `_hot_streak('hot2', 15, 4)` | Горячая серия: 15 тиражей, порог 4 |
| p106 | `_gap_acceleration` | Ускорение разрывов (gap acceleration) |
| p107 | `_sum_parity` | Анализ чётности/нечётности суммы |
| p108 | `_consecutive_pairs` | Анализ последовательных пар |
| p109 | `_high_low_split` | Разделение high/low чисел |
| p110 | `_differential_freq` | Дифференциальная частота |
| p111 | `_triple_markov` | Тройная марковская цепь |
| p112 | `_entropy_weighted` | Энтропийно-взвешенный отбор |
| p113 | `_mean_reversion('mrev1', 50)` | Средняя реверсия (50 тиражей) |
| p114 | `_mean_reversion('mrev2', 100)` | Средняя реверсия (100 тиражей) |
| p115 | `_mean_reversion('mrev3', 150)` | Средняя реверсия (150 тиражей) |
| p116 | `_lag_correlation` | Корреляция с лагом |
| p117 | `_block_sum_trend` | Тренд суммы блоков |
| p118 | `_monte_carlo_bayesian` | Монте-Карло + байесовская оценка |
| p119 | `_recency_z(150)` | Z-score на 150 тиражах |
| p120 | `_bayesian(1.0)` | Байесовская оценка с balanced prior |

##### G8: Дополнительные модели (13 моделей, p121-p133)

| ID | Название | Алгоритм |
|---|---|---|
| p121 | `_adaptive_ewma` | Адаптивное EWMA (α зависит от волатильности) |
| p122 | `_gap_burst` | Обнаружение «burst» паттернов в разрывах |
| p123 | `_cluster_analysis` | Кластерный анализ чисел по частоте |
| p124 | `_position_specific('pos0', 0)` | Позиционная модель для P0 |
| p125 | `_position_specific('pos1', 1)` | Позиционная модель для P1 |
| p126 | `_position_specific('pos2', 2)` | Позиционная модель для P2 |
| p127 | `_position_specific('pos3', 3)` | Позиционная модель для P3 |
| p128 | `_window(8)` | Короткое окно 8 тиражей |
| p129 | `_window(12)` | Окно 12 тиражей |
| p130 | `_window(40)` | Окно 40 тиражей |
| p131 | `_window(250)` | Длинное окно 250 тиражей |
| p132 | `_bayesian(1.5)` | Байесовская оценка со слабым prior |
| p133 | `_draw_type_specific` | Специфичные для типа тиража частоты |

##### G9/G10: DISABLED (v25.0)

22 модели были отключены в v25.0:
- **G9** (15 моделей): anti-consensus, positional frequency, spread, combo — предсказывали числа, которые большинство отвергало
- **G10** (7 моделей): triplet-based, additional anti-consensus — анализировали часто встречающиеся тройки

**Причина**: эти модели чаще снижали точность, чем повышали. Их «противоположные» прогнозы разбавляли консенсус здоровых моделей.

#### `TOTAL_MODELS = 133`

### 7.3. Класс FreqCache — Кэш частот и разрывов

```python
class FreqCache:
    """Кэш частот появления и разрывов для каждого числа."""
    
    def __init__(self, draws, b1_max=None, b2_max=None):
        self.b1f = defaultdict(int)   # block1 частоты: {number: count}
        self.b2f = defaultdict(int)   # block2 частоты
        self.ls1 = {}                 # block1 last_seen: {number: last_index}
        self.ls2 = {}                 # block2 last_seen
        self.n = len(draws)
    
    def gap1(self, x):
        """Сколько тиражей прошло с последнего появления."""
        ls = self.ls1.get(x, -1)
        return self.n - ls - 1 if ls >= 0 else self.n
    
    def aff(self, x):
        """Аффинитет числа к block1 vs block2 (0-1)."""
        b1 = self.b1f.get(x, 0)
        b2 = self.b2f.get(x, 0)
        tot = b1 + b2
        return b1 / tot if tot > 0 else 0.5
```

### 7.4. Класс DualBayesRing — Байесовский трекер весов

Отслеживает эффективность каждой из 133 моделей **отдельно для STD и RNG тиражей**:

```python
class DualBayesRing:
    def __init__(self, n=133, maxr=200, tau=30.0):
        self._rings = {'std': [], 'rng': [], 'all': []}
    
    def update(self, preds, ab1, ab2, draw_type='all'):
        """Обновляет веса после каждого тиража."""
        h1 = [len(set(b1) & set(ab1)) for b1, b2 in preds]
        h2 = [len(set(b2) & set(ab2)) for b1, b2 in preds]
        entry = {'h1': h1, 'h2': h2, 'h': h1 + h2}
        # FIFO кольцо (max 200 записей)
        self._rings['all'].insert(0, entry)
    
    def weights(self, draw_type='all'):
        """Возвращает веса моделей (w1 для block1, w2 для block2)."""
        # Экспоненциальное затухание: d = exp(-age / tau)
        # Weight decay: штраф ×0.5 за отсутствие попаданий в последних 20
```

**Формула комбинированного веса**:
```python
w1, w2 = bayes.weights(draw_type)
combined = np.sqrt(w1 * w2)  # геометрическое среднее
```

Почему `sqrt(w1 * w2)`: штрафует модели, хорошо работающие только на одном типе тиражей. Если модель идеальна для STD (w1=5) но бесполезна для RNG (w2=1), вес = √5 ≈ 2.24, а не 3 (арифметическое среднее).

### 7.5. `b1b2_from_scores()` — Преобразование scores в предсказание

```python
def b1b2_from_scores(sb1, sb2, b1_max=None, b2_max=None):
    """Словари {number: score} → отсортированные списки чисел."""
    # os.urandom для уникального шума (разрыв связей)
    _seed = int.from_bytes(os.urandom(4), 'big')
    _rng_noise = np.random.default_rng(_seed)
    _noise1 = _rng_noise.uniform(0, 0.001, size=b1_max)
    
    # Топ PICK_B1 чисел из sb1 + шум
    top4b1 = sorted(range(1, b1_max + 1),
                    key=lambda x: -(sb1.get(x, 0) + _noise1[x - 1]))[:PICK_B1]
    return sorted(top4b1), sorted(top4b2)
```

### 7.6. `predict.py` — CLI-обёртка ML-движка

**Файл**: `python/predict.py` (1494 строки)

#### Мокирование Streamlit

Ключевое решение: `predict.py` мокирует модуль `streamlit` перед импортом `lp_v130_app.py`:

```python
class _MockST:
    """Универсальный мок для всех Streamlit-вызовов."""
    def __call__(self, *a, **kw):
        return _MOCK_RETURN
    def __getattr__(self, name):
        if name == 'session_state':
            return _MOCK_SESSION_STATE
        return _MOCK_RETURN

sys.modules['streamlit'] = st_mock  # подмена модуля

from lp_v130_app import (LP132, DualBayesRing, FreqCache, ...)
```

#### Training Pipeline (`run_training()`)

```
1. Seed phase: инициализация предиктора на первых seed_size тиражей
2. Batch loop: обработка батчами по batch_step (по умолчанию 50) тиражей
3. Per-draw: быстрое предсказание через _fast_pred (16 моделей)
4. Full ensemble: полная оценка всех 133 моделей каждые full_every (по умолчанию 3) батчей
5. DualBayesRing: обновление весов моделей по точности
6. Final: полная оценка + взвешенный консенсус
```

#### `_fast_pred` — Быстрое предсказание во время обучения

Использует **16 разнообразных моделей** для быстрой оценки (вместо 133 полных):

```python
def _fast_pred(predictor, bayes, draw_type='all'):
    # Base models (G1): freq, markov, gap, momentum, zscore, entropy
    # Position-specific (G8): pos0, pos1
    # Entropy-weighted (G7)
    # Gap+Freq (G3)
    # Draw-type-specific (G8)
    # Velocity (G5)
```

#### Дополнительные алгоритмы в predict.py

- **`build_backtest_heatmap()`**: структурированные данные бэктеста по тиражам с лучшей моделью
- **`build_frequency_analysis()`**: per-number частота + last_seen
- **`build_pair_analysis()`**: топ-10 наиболее частых пар чисел в block1
- **`build_gap_analysis()`**: overdue числа с gap/avg_gap/overdue_score
- **`build_sum_range_stats()`**: исторические распределения суммы и диапазона
- **`compute_top5_models()`**: рейтинг моделей по средней точности
- **`_monte_carlo_confidence()`**: 5000 итераций Монте-Карло
- **`_k_fold_cross_validation()`**: k-fold кросс-валидация
- **`_fetch_game_schedule()`**: определение типа тиража (RNG/TV) из правил stoloto.ru

#### Output (JSON в stdout)

```json
{
  "status": "ok",
  "game": "4x20",
  "game_format": { "pick_b1": 4, "pick_b2": 4, "b1_max": 20, "b2_max": 20, "total_models": 133 },
  "data_quality": { "total_draws": 13000, "missing": 0, "has_gaps": false },
  "prediction": {
    "block1": [3, 7, 13, 18],
    "block2": [2, 9, 14, 17],
    "consensus_agreement_b1": 0.42,
    "consensus_agreement_b2": 0.38,
    "consensus_votes_b1": { "3": 45, "7": 42, ... },
    "consensus_votes_b2": { "2": 38, "9": 35, ... }
  },
  "accuracy": {
    "last_50_avg": 2.8,
    "last_100_avg": 2.6,
    "baseline_random": 1.6,
    "improvement_pct": 75.0
  },
  "backtest": {
    "heatmap": [ { "draw_num": 13279, "act_b1": [...], "pred_b1": [...], "hits_b1": 2, "best_model": {...} }, ... ],
    "last_50_avg": 2.8
  },
  "monte_carlo": { "iterations": 5000, "mean": 2.8, "p5": 1.0, "p95": 5.0, "p_ge5": 0.12 },
  "cross_validation": { "mean_score": 2.5, "std_score": 0.8, "folds": [...] },
  "top5_models": { "ranking": [...], "predictions": [...] },
  "analysis_methods": ["freq", "markov", "gap", ...],
  "sum_range_stats": { ... },
  "cross_game_analysis": { ... },
  "pair_analysis": { "top_pairs": [...] },
  "gap_analysis": { "overdue": [...] },
  "frequency_analysis": { ... },
  "draw_schedule": { "draw_type": "std", "is_predictable": true, "draw_type_label": "..." }
}
```

### 7.7. `pipeline.py` — Позиционный ансамбль

**Файл**: `python/pipeline.py` (694 строки)

Читает `model_report_data` (созданный predict.py) и выполняет:

1. **Position-based voting**: для каждой позиции (P0, P1, P2, P3) — голосование всех моделей
2. **Accuracy-weighted votes**: правильные прогнозы получают больший вес (×2.0)
3. **Frequency prediction**: `recency_score = count × (1 / (1 + last_seen))`
4. **Top-3 models**: 3 лучших модели по недавней точности
5. **Number spectrum**: агрегированные голоса по всем позициям

**Команда**:
```bash
python3 pipeline.py --game 4x20 [--type std|rng] [--top 30] [--recency 200]
```

### 7.8. `analyze.py` — Анализатор 38 игр

**Файл**: `python/analyze.py` (335 строк)

Два режима:
```bash
# Быстрый: только список игр из API (~5-15 сек)
python3 analyze.py --list-only

# Полный: анализ всех игр с chi2 + autocorrelation (~6 мин, кэш 7 дней)
python3 analyze.py
```

`stoloto_analyzer_v3.py` предоставляет:
- `get_games()`: GET-запрос к stoloto.ru API → список активных игр
- `game_exists_on_site()`: проверка существования игры (с кэшем)
- `fetch_draws(game, max_draws)`: пагинационная загрузка тиражей
- `GameStats`: chi2-тест, автокорреляция, hot/cold числа, cross-game correlation

### 7.9. `fetch_draws.py` — Загрузка тиражей

**Файл**: `python/fetch_draws.py` (935 строк)

Ключевые возможности:

- **Автоопределение первого тиража**: бинарный поиск по год → месяц → день (~25 запросов)
- **Заполнение пропусков**: если файл существует — ищет пропущенные номера тиражей
- **5 форматов API stoloto.ru**: flat list, played/notPlayed dict, list-of-dicts, и др.
- **GAME_FORMAT_HINTS**: формат для 44 игр (pick_b1, pick_b2, b1_max, b2_max)
- **Retry + rate-limit**: обработка HTTP 429 с экспоненциальным ожиданием
- **Пост-записная валидация**: `_validate_written_file()` проверяет последние 5 строк
- **3-level fallback** при ошибке бинарного поиска: last year, SEARCH_EPOCH (2009), 2020-01-01

### 7.10. `lottery_pipeline.py` — Движок pipeline

**Файл**: `python/lottery_pipeline.py` (1071 строка)

Основная функция `analyze_from_pipeline_data()`:
- Парсинг HTML/CSV данных из model_report
- Позиционное голосование по всем моделям
- Accuracy-weighted ensemble (50% голосование + 50% accuracy-weighted)
- Confidence scoring
- Number spectrum с recency weighting

### 7.11. GAME_FORMAT_HINTS — Форматы 44 игр

Словарь `GAME_FORMAT_HINTS` определён в 3 файлах (lp_v130_app.py, pipeline.py, fetch_draws.py):

```python
GAME_FORMAT_HINTS = {
    '4x20':        {'pick_b1': 4, 'pick_b2': 4, 'b1_max': 20, 'b2_max': 20},
    '6x45plus':    {'pick_b1': 6, 'pick_b2': 1, 'b1_max': 45, 'b2_max': 4},
    '5x36plus':    {'pick_b1': 5, 'pick_b2': 1, 'b1_max': 36, 'b2_max': 4},
    '5x2':         {'pick_b1': 5, 'pick_b2': 2, 'b1_max': 50, 'b2_max': 10},
    'keno2':       {'pick_b1': 1, 'pick_b2': 1, 'b1_max': 20, 'b2_max': 10},
    '7x49':        {'pick_b1': 7, 'pick_b2': 0, 'b1_max': 49, 'b2_max': 0},
    # ... и ещё 38 игр
}
```

---

## 8. Инфраструктура

### 8.1. `python-runner.ts` — Кроссплатформенный запуск Python

**Файл**: `src/lib/python-runner.ts`

Автоматический поиск Python с нужными пакетами (numpy + requests):

```
Приоритет поиска:
  1. /home/z/.venv/bin/python3, python         (Linux sandbox)
  2. $HOME/.venv/bin/python3, python           (user venv)
  3. $HOME/.local/bin/python3                  (pip --user)
  4. $CONDA_PREFIX/bin/python3                 (Conda)
  5. $USERPROFILE\.venv\Scripts\python.exe     (Windows venv)
  6. $LOCALAPPDATA\Programs\Python\Python312   (Windows installers)
  7. System PATH: python3, python, py          (fallback)
```

**Проверка**: `python -c "import numpy; import requests; print('OK')"` — результат memoised после первого успешного разрешения.

**Запуск скрипта**: `runPythonScript(scriptName, args, { timeout })`:
- На Linux/macOS: `spawn(python, [scriptPath, ...args])` — без shell
- На Windows: `spawn(fullCmd, [], { shell: true })` — с shell для PATH
- Таймаут по умолчанию: 10 минут (600000ms)
- Переменная окружения `PYTHONIOENCODING=utf-8`

### 8.2. `background-cache.ts` — Общий обработчик кэша

**Файл**: `src/lib/background-cache.ts`

Центральный модуль для predict и pipeline. Реализует паттерн **cache-first + background execution**:

```typescript
interface CacheConfig {
  cacheTtl?: number           // по умолчанию 30 мин
  maxCacheEntries?: number    // по умолчанию 20
  rateLimitMax?: number       // по умолчанию 3
  rateLimitWindowMs?: number  // по умолчанию 60_000
  scriptName: string          // имя Python-скрипта
  scriptArgs?: (...) => string[]
  timeoutMs?: number          // по умолчанию 600_000 (10 мин)
  operationLabel: string      // 'predict' | 'pipeline'
}
```

Каждый вызов:
1. Проверяет rate limit → 429 если превышен
2. Валидирует `game` и `file` параметры
3. Проверяет кэш по ключу `game + fileModTime` → возвращает если свежий
4. Запускает фоновое выполнение через `runPythonScript`
5. Возвращает stale-кэш или `status: 'pending'`

**Эвикция**: max 20 записей, oldest-first удаление.

### 8.3. `rate-limit.ts` — In-memory rate limiter

**Файл**: `src/lib/rate-limit.ts`

```typescript
rateLimit(key: string, maxRequests = 5, windowMs = 60_000): RateLimitResult
// Возвращает: { allowed: boolean, remaining: number, resetIn: number }
```

- **Автоочистка**: истёкшие записи удаляются при каждом вызове через `_evict()`
- **MAX_ENTRIES = 500**: при превышении — удаляются самые старые
- **Ключ**: `{operationLabel}-{game}` (например, `predict-4x20`)

### 8.4. `fetch.ts` — Безопасный JSON-запрос

**Файл**: `src/lib/fetch.ts`

```typescript
safeJsonFetch<T>(url: string, options?: RequestInit, timeoutMs?: number): SafeFetchResult<T>
```

Защита от распространённых ошибок:
- **Таймаут** через `AbortController` + `DOMException('Timeout', 'TimeoutError')`
- **HTML-детекция**: проверка `text.trimStart().startsWith('<')` перед JSON.parse
- **Content-Type валидация**: проверка `res.headers.get('content-type').includes('application/json')`
- **HTTP error handling**: проверка `res.ok` + попытка извлечь JSON error body

### 8.5. `adapters.ts` — Типобезопасное преобразование данных

**Файл**: `src/lib/adapters.ts`

Два основных адаптера с безопасными хелперами `num()`, `str()`, `arr()`, `rec()`, `dig()`:

```typescript
adaptPredictResult(raw: Record<string, unknown>): PredictionResult
adaptPipelineResult(raw: Record<string, unknown>, fallbackGameKey: string): PipelineResult
```

Каждый адаптер:
- Извлекает данные с fallback-значениями по умолчанию
- Проверяет наличие вложенных полей
- Обрабатывает отсутствующие опциональные поля (backtest, monte_carlo, cross_validation)
- Преобразует snake_case в camelCase

### 8.6. `api-utils.ts` — Общие утилиты API

**Файл**: `src/lib/api-utils.ts`

- **`DATA_DIR`**: `join(ROOT, 'data', 'draws')` — персистентная директория тиражей
- **`ensureDataDir()`**: создание директории при необходимости
- **`getDrawsFilePath(game)`**: `data/draws/draws_{game}.txt`
- **`countDrawsInFile(filePath)`**: кэшированный подсчёт строк (5-min TTL, max 50 entries)
- **`safeParseStdout(stdout)`**: парсинг stdout Python — только JSON (начинается с `{` или `[`)
- **`validateGameId(game)`**: только `a-z0-9+_`, max 50 символов
- **`validateFilePath(path)`**: только DATA_DIR или /tmp/, отклоняет `..`
- **`KNOWN_GAMES`**: Set с 50+ известными идентификаторами игр

### 8.7. `usePolling.ts` — Хук поллинга

**Файл**: `src/hooks/usePolling.ts`

```typescript
const { startPolling, versionRef } = usePolling({
  maxRetries: 60,    // макс. попыток (5 мин при 5s interval)
  delayMs: 5000,     // интервал между попытками
  onError: (err) => { /* сетевая ошибка — остановить поллинг */ }
})
```

Использование:
```typescript
startPolling(async () => {
  const res = await fetch('/api/lottery/predict', { ... })
  const data = await res.json()
  if (data.status === 'ok') return false  // данные получены — стоп
  return true  // ещё pending — продолжать
})

// Отмена всех текущих поллингов:
versionRef.current++
```

### 8.8. `db.ts` — Prisma клиент

**Файл**: `src/lib/db.ts`

```typescript
import { PrismaClient } from '@prisma/client'
const prisma = new PrismaClient()
export default prisma
```

---

## 9. База данных

### 9.1. Схема Prisma

**Файл**: `prisma/schema.prisma`

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL")
}
```

### 9.2. Модели

#### GameAnalysis — Снимок анализа игры

```prisma
model GameAnalysis {
  id            String   @id @default(cuid())
  gameKey       String   @unique
  gameName      String
  score         Float                    // Оценка аномальности (0-100)
  verdict       String                   // high_anomaly | moderate_anomaly | normal | insufficient
  verdictColor  String   @default("green")
  draws         Int      @default(0)     // Количество проанализированных тиражей
  chi2P         Float?                   // p-value chi-squared теста
  autocorr      Float?                   // Коэффициент автокорреляции
  hotNumbers    String   @default("[]")  // JSON массив горячих чисел
  coldNumbers   String   @default("[]")  // JSON массив холодных чисел
  redirectTarget String?                 // Перенаправление на другую игру
  analyzedAt    DateTime @default(now())
  updatedAt     DateTime @updatedAt
}
```

#### PredictionLog — Лог прогнозов

```prisma
model PredictionLog {
  id            String   @id @default(cuid())
  gameKey       String                   // Идентификатор игры
  totalDraws    Int                      // Количество тиражей использованных
  modelsUsed    Int                      // Количество моделей (133)
  consensusB1   Float?                   // Консенсус block1
  consensusB2   Float?                   // Консенсус block2
  backtestAvg50 Float?                   // Средняя точность за 50 тиражей
  createdAt     DateTime @default(now())
}
```

### 9.3. Управление

```bash
bun run db:push       # Применить схему к БД без миграций
bun run db:generate   # Сгенерировать Prisma Client
bun run db:migrate    # Создать и применить миграцию
bun run db:reset      # Сбросить БД
```

---

## 10. Безопасность

### 10.1. Валидация идентификатора игры (`validateGameId`)

```typescript
export function validateGameId(game: unknown): string | null {
  if (typeof game !== 'string' || game.length === 0 || game.length > 50) {
    return 'Game must be a non-empty string (max 50 chars)'
  }
  if (!/^[a-z0-9+_]+$/i.test(game)) {
    return 'Game identifier contains invalid characters'
  }
  if (!KNOWN_GAMES.has(game)) {
    console.warn(`[api] Unknown game identifier: "${game}"`)  // предупреждение, но не блокировка
  }
  return null
}
```

**Защита**:
- Только `[a-z0-9+_]` — никаких спецсимволов, пробелов, path separators
- Макс. 50 символов — предотвращает buffer overflow
- Предупреждение для неизвестных игр — новые игры не блокируются

### 10.2. Защита от path traversal (`validateFilePath`)

```typescript
export function validateFilePath(filePath: unknown): string | null {
  if (typeof filePath !== 'string' || filePath.length === 0) {
    return 'File path must be a non-empty string'
  }
  if (filePath.includes('..')) {
    return 'Path traversal detected'
  }
  if (filePath.startsWith(DATA_DIR)) return null     // data/draws/
  if (filePath.startsWith(tmpdir())) return null     // OS temp
  if (filePath.startsWith('/tmp/')) return null      // Unix temp
  return 'File path must be under data or temp directory'
}
```

**Защита**:
- Отклоняет `..` — классическая path traversal атака
- Белый список директорий: только DATA_DIR и /tmp/
- Не допускает произвольные пути к файлам системы

### 10.3. Rate Limiting

| Эндпоинт | Лимит | Окно |
|---|---|---|
| Analyze | Без лимита | — |
| Fetch-draws | 5 запросов | 60 сек (на игру) |
| Predict | 3 запроса | 60 сек (на игру) |
| Pipeline | 3 запроса | 60 сек (на игру) |

Ответ при превышении:
```json
{
  "error": "Слишком много запросов. Подождите 30с и попробуйте снова.",
  "retry_after": 30
}
```
HTTP статус: `429 Too Many Requests` + заголовок `Retry-After`.

### 10.4. Безопасный парсинг stdout

```typescript
export function safeParseStdout(stdout: string) {
  const trimmed = stdout.trim()
  // Парсим ТОЛЬКО если начинается с { или [
  if (trimmed[0] === '{' || trimmed[0] === '[') {
    return { data: JSON.parse(trimmed) }
  }
  return { error: `Script returned non-JSON output (starts with "${trimmed.slice(0, 50)}")` }
}
```

Защита от инъекции: если Python-скрипт выводит не-JSON (например, HTML от ошибки), парсер отклоняет вывод.

### 10.5. Content-Type проверка

`safeJsonFetch` проверяет заголовок `Content-Type` перед `res.json()`:
- Если Content-Type не содержит `application/json` — проверяет текст на HTML
- Если ответ начинается с `<` — возвращает ошибку «Сервер вернул HTML вместо JSON»

---

## 11. UX/UI

### 11.1. Дизайн-решения

- **Тёмная тема**: градиентный фон (`bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950`)
- **Цветовая семантика**: красный = высокая аномалия, amber = умеренная, зелёный = норма, серый = недостаточно данных
- **Блоки чисел**: Block 1 = синий (`blue`), Block 2 = изумрудный (`emerald`)
- **Статические классы Tailwind**: все динамические цвета через `BLOCK_COLOR_CLASSES` mapping (purge-safe)
- **Шрифт**: системный (system-ui) через `next/font`

### 11.2. 4-шаговый Wizard

| Шаг | Название | Действие | Длительность |
|---|---|---|---|
| 1 | Анализ | Автоматический анализ 38 игр | 5-15 сек (cached: мгновенно) |
| 2 | Тиражи | Выбор игры + загрузка тиражей | 30 сек - 3 мин (cached: мгновенно) |
| 3 | Прогноз | Запуск 133 ML-моделей | 1-3 мин (cached: мгновенно) |
| 4 | Pipeline | Позиционный ансамбль (auto) | 30-60 сек (cached: мгновенно) |

Навигация: кнопки «Далее»/«Назад», клавиши ← →.

### 11.3. Анимации (framer-motion)

- **Wizard transitions**: spring-based анимация переключения шагов (`AnimatePresence`)
- **Анимированное раскрытие чисел**: числа прогноза появляются по одному с spring-анимацией (`staggerChildren: 0.1`)
- **Collapse/expand**: heatmap строки (`AnimatePresence` + `motion.div`)
- **Reduced motion**: `usePrefersReducedMotion()` отключает анимации при `prefers-reduced-motion: reduce`

### 11.4. Доступность (Accessibility)

| Элемент | ARIA |
|---|---|
| Шаги wizard | `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls` |
| Содержимое шага | `role="tabpanel"`, `aria-labelledby` |
| Ошибки | `role="status"`, `aria-live="polite"` |
| Загрузка | `role="status"`, `aria-live="polite"` |
| Карточки игр | `role="option"`, `aria-selected` |
| HeatmapRow | `aria-expanded` |
| CopyButton | `<span className="sr-only">Копировать</span>` |
| Focus | `focus-visible:ring-2 focus-visible:ring-blue-500` на всех интерактивных элементах |
| Touch targets | мин. 44px высота на step indicator и game list |

### 11.5. Адаптивный дизайн (Responsive)

- **Mobile-first**: `use-mobile.ts` хук для определения мобильного устройства
- **Touch targets**: мин. 44px для кнопок навигации и выбора игр
- **Responsive grid**: карточки игр перестраиваются в колонку на маленьких экранах
- **Scrollable**: длинные списки и heatmap обёрнуты в scrollable контейнеры

### 11.6. Toast-уведомления (sonner)

Используется библиотека `sonner` для контекстных уведомлений:
- Успех: «Тиражи загружены: 13 310»
- Ошибка: «Ошибка анализа: ...»
- Копирование: «Скопировано в буфер обмена»
- Поддержка русской локализации

---

## 12. Кэширование

### 12.1. Многоуровневая стратегия

```
┌─────────────────────────────────────────────────────────────┐
│                    ЗАПРОС К API                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  L1: In-memory cache (Map в Node.js процессе)               │
│  ├── Analyze: singleton, 30 min TTL                         │
│  ├── Predict: Map<game, CacheEntry>, 30 min TTL, max 20     │
│  ├── Pipeline: Map<game, CacheEntry>, 30 min TTL, max 20    │
│  ├── Draw counts: Map<file, {count, ts}>, 5 min TTL, max 50│
│  └── Rate limits: Map<key, {count, resetTime}>, max 500    │
└────────────────────┬────────────────────────────────────────┘
                     │ miss
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  L2: Файловый кэш Python                                    │
│  ├── analyze: stoloto_analysis_v3.json (7 day TTL)          │
│  ├── fetch-draws: data/draws/draws_{game}.txt (persistent)  │
│  └── predict/pipeline: /tmp/pipeline_data_{game}.json       │
└────────────────────┬────────────────────────────────────────┘
                     │ miss / stale
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  L3: Background execution (child_process.spawn)             │
│  ├── Таймаут: 15 сек (--list-only) → 10 мин (predict)      │
│  ├── Только один фоновый процесс на операцию + игру         │
│  └── Результат записывается в L1 + L2                       │
└─────────────────────────────────────────────────────────────┘
```

### 12.2. Детали по операциям

| Операция | In-memory TTL | Файл кэш | Фоновое обновление | Client polling |
|---|---|---|---|---|
| **Analyze** | 30 мин | `stoloto_analysis_v3.json` (7 дней) | Да, fire-and-forget | 5s, 60 max |
| **Fetch-draws** | — (file cache) | `data/draws/draws_{game}.txt` (persistent) | Да, 2-min cooldown | 5s, 60 max |
| **Predict** | 30 мин | — (только L1 + L3) | Да, cache-first + bg | 5s, 60 max |
| **Pipeline** | 30 мин | — (только L1 + L3) | Да, cache-first + bg | 5s, 60 max |
| **Draw counts** | 5 мин | — | — | — |

### 12.3. Инвалидация кэша

| Операция | Триггер инвалидации |
|---|---|
| Predict | Изменение `fileModTime` файла тиражей |
| Pipeline | Изменение `fileModTime` файла тиражей |
| Analyze | Истечение TTL (30 мин) или параметр `refresh: true` |
| Fetch-draws | 2-минутный cooldown после последнего обновления |

### 12.4. Защита от переполнения памяти

- **Predict/Pipeline cache**: max 20 записей, oldest-first eviction
- **Draw counts cache**: max 50 записей, oldest-first eviction
- **Rate limits**: max 500 записей, автоочистка `_evict()` при каждом вызове
- **Один фоновый процесс**: флаг `refreshingMap[game]` предотвращает дублирование

### 12.5. Файловая персистентность

```
data/draws/draws_4x20.txt         — persists across restarts
data/draws/draws_6x45plus.txt     — persists across restarts
python/stoloto_analysis_v3.json   — 7 day TTL
/tmp/model_report_4x20.json       — cleared on reboot
/tmp/pipeline_data_4x20.json      — cleared on reboot
sessionStorage:lp_state            — cleared on tab close
```

---

## 13. Зависимости

### 13.1. Runtime зависимости

| Пакет | Версия | Назначение |
|---|---|---|
| `next` | 16.1+ | Full-stack React фреймворк: App Router, API Routes, SSR |
| `react` | 19.0 | UI библиотека: компоненты, hooks, concurrent features |
| `react-dom` | 19.0 | DOM rendering для React 19 |
| `framer-motion` | 12.23+ | Анимации: wizard transitions, number reveal, collapse |
| `@prisma/client` | 6.11+ | Type-safe ORM client для SQLite |
| `prisma` | 6.11+ | ORM toolkit: schema definition, migrations, codegen |
| `sonner` | 2.0+ | Toast-уведомления: лёгкие, кастомизируемые, dark theme |
| `lucide-react` | 0.525+ | Иконки: ExternalLink, Copy, Check, и др. |
| `tailwind-merge` | 3.3+ | Слияние Tailwind классов без конфликтов (для `cn()`) |
| `clsx` | 2.1+ | Утилита условных CSS классов |
| `class-variance-authority` | 0.7+ | Варианты компонентов (для shadcn/ui) |
| `zod` | 4.0+ | Schema validation (для react-hook-form) |
| `date-fns` | 4.1+ | Работа с датами (форматирование, сравнение) |
| `zustand` | 5.0+ | Лёгкий state manager (установлен, может использоваться в будущем) |
| `recharts` | 2.15+ | Графики и диаграммы (установлен, может использоваться) |
| `uuid` | 11.1+ | Генерация UUID (для Prisma @default(cuid())) |
| `sharp` | 0.34+ | Обработка изображений (Next.js Image optimization) |

### 13.2. shadcn/ui компоненты (Radix UI)

Установлены ~40 пакетов `@radix-ui/*`:

| Пакет | Компонент |
|---|---|
| `@radix-ui/react-accordion` | Аккордеон (collapse/expand) |
| `@radix-ui/react-alert-dialog` | Диалог подтверждения |
| `@radix-ui/react-avatar` | Аватар пользователя |
| `@radix-ui/react-checkbox` | Чекбокс |
| `@radix-ui/react-collapsible` | Сворачиваемый контент |
| `@radix-ui/react-dialog` | Модальное окно |
| `@radix-ui/react-dropdown-menu` | Выпадающее меню |
| `@radix-ui/react-label` | Лейбл формы |
| `@radix-ui/react-popover` | Popover (всплывающий элемент) |
| `@radix-ui/react-progress` | Прогресс-бар |
| `@radix-ui/react-scroll-area` | Скроллируемая область |
| `@radix-ui/react-select` | Select (выпадающий список) |
| `@radix-ui/react-separator` | Разделитель |
| `@radix-ui/react-slider` | Слайдер |
| `@radix-ui/react-slot` | Slot для составных компонентов |
| `@radix-ui/react-switch` | Переключатель |
| `@radix-ui/react-tabs` | Табы |
| `@radix-ui/react-toast` | Toast уведомления |
| `@radix-ui/react-tooltip` | Тултип |
| `@radix-ui/react-toggle` | Кнопка-переключатель |
| `@radix-ui/react-toggle-group` | Группа кнопок-переключателей |
| ... и ещё ~20 пакетов |卡片, menubar, navigation, resizable, и др. |

### 13.3. Dev зависимости

| Пакет | Назначение |
|---|---|
| `typescript` | 5.x — компилятор TypeScript |
| `@types/react` | Type definitions для React 19 |
| `@types/react-dom` | Type definitions для ReactDOM |
| `tailwindcss` | 4.x — CSS framework |
| `@tailwindcss/postcss` | PostCSS плагин для Tailwind 4 |
| `eslint` | 9.x — линтер |
| `eslint-config-next` | ESLint конфигурация для Next.js 16 |
| `bun-types` | Type definitions для Bun runtime |

### 13.4. Python-зависимости

| Пакет | Назначение |
|---|---|
| `numpy` | Векторные вычисления: частоты, random, array operations для 133 моделей |
| `scipy` | Статистика: chi2_contingency, pearsonr (автокорреляция) |
| `requests` | HTTP-клиент для stoloto.ru API |

---

## Приложение A: Шлюз Caddy

**Файл**: `Caddyfile`

```caddyfile
:81 {
    @transform_port_query {
        query XTransformPort=*
    }

    handle @transform_port_query {
        reverse_proxy localhost:{query.XTransformPort}
    }

    handle {
        reverse_proxy localhost:3000 {
            flush_interval -1
            transport http {
                read_timeout 900s     # 15 минут для длинных Python-запросов
                write_timeout 900s
            }
        }
    }
}
```

- **Порт 81** (внешний) → порт 3000 (Next.js)
- **`XTransformPort`**: query-параметр для маршрутизации к мини-сервисам
- **`flush_interval -1`**: немедленная отправка chunked response
- **15-минутные таймауты**: предотвращает разрыв соединений при длинных Python-вычислениях

## Приложение B: Формат файлов тиражей

Файлы тиражей хранятся в `data/draws/draws_{game}.txt`:

**4-частный формат** (предпочтительный):
```
DATE||NUMBER||BLOCK1||BLOCK2
11.04.2026 23:22||13280||20,7,13,1||18,17,14,9
11.04.2026 20:00||13279||3,12,15,18||5,8,11,16
```

**3-частный формат** (legacy, автоматически конвертируется):
```
DATE||NUMBER||ALL_NUMBERS
11.04.2026 23:22||13280||20,7,13,1,18,17,14,9
```

Разделитель блоков: при 3-частном формате числа разделяются по `GAME_FORMAT_HINTS` (pick_b1, pick_b2).

---

*Документация обновлена: версия 30.0. Всего Python-кода: 5381 строк. ML-моделей: 133. Анализируемых игр: 38.*
