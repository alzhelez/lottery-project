# План автотестирования — Локальный предсказатель v36.0

> **Проект:** /home/z/my-project
> **Дата:** Июль 2025
> **Версия документа:** 3.0 — Оптимизированная версия
> **Статус:** Оптимизированный план (v2.0 → v3.0, −29 % тест-кейсов)

---

## Содержание

1. [Обзор и цели](#1-обзор-и-цели)
2. [Рекомендуемые инструменты](#2-рекомендуемые-инструменты)
3. [Структура директории тестов](#3-структура-директории-тестов)
4. [Unit-тесты — утилиты TypeScript (vitest)](#4-unit-тесты--утилиты-typescript-vitest)
5. [Unit-тесты — React-хуки (vitest)](#5-unit-тесты--react-хуки-vitest)
6. [Компонентные тесты (React Testing Library)](#6-компонентные-тесты-react-testing-library)
7. [Тестирование ErrorBoundary](#7-тестирование-errorboundary)
8. [Интеграционные тесты — API-маршруты](#8-интеграционные-тесты--api-маршруты)
9. [E2E-тесты — полный мастер](#9-e2e-тесты--полный-мастер)
10. [Unit-тесты — Python (pytest)](#10-unit-тесты--python-pytest)
11. [Интеграционные Python E2E-тесты](#11-интеграционные-python-e2e-тесты)
12. [Методология проверки покрытия](#12-методология-проверки-покрытия)
13. [Сводная таблица тестов](#13-сводная-таблица-тестов)
14. [Запуск тестового набора](#14-запуск-тестового-набора)
15. [Конфигурационные файлы](#15-конфигурационные-файлы)

---

## 1. Обзор и цели

### 1.1 Архитектура проекта

Проект «Локальный предсказатель» v36.0 представляет собой SPA-приложение для анализа и предсказания результатов лотерей. Состоит из трёх уровней:

- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui, framer-motion
- **Backend:** Next.js API-маршруты, которые спавнят Python-скрипты
- **ML-движок:** Python (predict.py, lp_v130_app.py, lottery_pipeline.py и др.)
- **База данных:** SQLite через Prisma (GameAnalysis + PredictionLog)

### 1.2 Ключевые модули для тестирования

| Уровень | Модули | Кол-во файлов |
|---------|--------|---------------|
| Python-скрипты | analyze, predict, pipeline, fetch, fetch_draws, lp_v130_app, lottery_pipeline | 7 |
| TS-утилиты | python-runner, background-cache, api-utils, rate-limit, fetch, adapters, db, utils | 8 |
| React-компоненты | types, CopyButton, StepIndicator, Step1-4, HeatmapRow, ErrorBoundary | 8 |
| React-хуки | usePolling, usePrefersReducedMotion | 2 |
| API-маршруты | analyze, fetch-draws, predict, pipeline, download-project | 5 |
| Страница | page.tsx, layout.tsx, globals.css | 3 |

### 1.3 Приоритеты

| Приоритет | Обозначение | Описание |
|-----------|-------------|----------|
| **P0** | Критический | Базовая функциональность. Без этих тестов релиз невозможен. |
| **P1** | Важный | Ключевые граничные случаи и стабильность. |

> **Примечание (v3.0):** Все P2-тесты удалены. Оставлены только P0 и P1.

### 1.4 Что изменилось в v3.0

| Оптимизация | Было | Стало | Δ |
|-------------|------|-------|---|
| Удаление P2-тестов | 28 тестов | 0 | −28 |
| Консолидация API (7.1–7.4) | 18 тестов, 4 секции | ~12 тестов, 1 секция | −6 |
| Консолидация Python predict (9.7–9.15) | 27 тестов, 9 секций | ~16 тестов, 2 файла | −11 |
| Консолидация E2E (8.1–8.3) | 13 тестов, 3 секции | 3 теста, 1 секция | −10 |
| Сокращение Python CLI | 9 тестов | 6 тестов | −3 |
| **Итого** | **234 / ~3025 LOC** | **~168 / ~2150 LOC** | **−28 %** |

---

## 2. Рекомендуемые инструменты

### 2.1 TypeScript / React

| Инструмент | Назначение | Версия |
|------------|-----------|--------|
| **Vitest** | Фреймворк для unit/интеграционных TS-тестов | ^2.x |
| **@testing-library/react** | Рендеринг компонентов в DOM | ^16.x |
| **@testing-library/jest-dom** | Расширения матчеров (toBeInTheDocument и пр.) | ^6.x |
| **@testing-library/user-event** | Симуляция действий пользователя | ^14.x |
| **msw (Mock Service Worker)** | Мокирование fetch/XMLHttpRequest | ^2.x |
| **jsdom** | Среда DOM для тестов | ^25.x |

### 2.2 Python

| Инструмент | Назначение | Версия |
|------------|-----------|--------|
| **pytest** | Фреймворк для тестов Python | ^8.x |
| **pytest-cov** | Измерение покрытия кода | ^6.x |
| **unittest.mock** | Встроенный мокинг (patch, MagicMock) | — |
| **responses** или **requests-mock** | Мокирование HTTP-запросов | ^0.25.x |

### 2.3 E2E

| Инструмент | Назначение | Версия |
|------------|-----------|--------|
| **Playwright** | E2E-тестирование браузера | ^1.x |

---

## 3. Структура директории тестов

```
tests/
├── python/                          # Python unit + E2E
│   ├── conftest.py                  # Общие fixture'ы (Draw, sample data)
│   ├── test_parse_line.py
│   ├── test_parse_text.py
│   ├── test_game_hints.py
│   ├── test_b1b2_from_scores.py
│   ├── test_freq_cache.py
│   ├── test_exp_w.py
│   ├── test_predict_helpers.py      # [v3.0] Консолидация: pair, gap, sum_range, cross_game, consensus
│   ├── test_predict_analysis.py     # [v3.0] Консолидация: frequency, heatmap, top5, time_weights
│   ├── test_pipeline_predict.py
│   ├── test_pipeline_analyze.py
│   ├── test_extract_blocks.py
│   ├── test_draw_to_line.py
│   ├── test_analyze_cli.py
│   ├── test_fetch_cli.py
│   ├── test_validate_written_file.py
│   ├── test_e2e_predict.py
│   └── test_e2e_pipeline.py
├── ts/                              # TypeScript unit
│   ├── rate-limit.test.ts
│   ├── safe-parse-stdout.test.ts
│   ├── validate-game-id.test.ts
│   ├── validate-file-path.test.ts
│   ├── count-draws.test.ts
│   ├── safe-json-fetch.test.ts
│   ├── adapt-predict.test.ts
│   ├── adapt-pipeline.test.ts
│   ├── python-runner.test.ts
│   ├── background-cache.test.ts
│   └── utils.test.ts
├── hooks/                           # React-хуки
│   ├── use-polling.test.ts
│   └── use-prefers-reduced-motion.test.ts
├── components/                      # React-компоненты
│   ├── types.test.ts
│   ├── CopyButton.test.tsx
│   ├── StepIndicator.test.tsx
│   ├── Step1Analysis.test.tsx
│   ├── Step2Draws.test.tsx
│   ├── Step3Predict.test.tsx
│   ├── Step4Pipeline.test.tsx
│   ├── HeatmapRow.test.tsx
│   └── ErrorBoundary.test.tsx
├── integration/                     # API-маршруты
│   ├── api-routes-contract.test.ts  # [v3.0] Объединённый: analyze, fetch-draws, predict, pipeline
│   ├── api-download-project.test.ts
│   └── full-flow.test.ts
└── e2e/                             # E2E (Playwright)
    └── full-wizard.spec.ts           # [v3.0] Только полный мастер
```

> **Изменения v3.0:**
> - Удалён `test_stoloto_api.py` (P2)
> - `test_pair_analysis.py`, `test_gap_analysis.py`, `test_sum_range.py`, `test_cross_game.py`, `test_consensus.py` → `test_predict_helpers.py`
> - `test_frequency.py`, `test_heatmap.py`, `test_top5.py`, `test_time_weights.py` → `test_predict_analysis.py`
> - `api-analyze.test.ts`, `api-fetch-draws.test.ts`, `api-predict.test.ts`, `api-pipeline.test.ts` → `api-routes-contract.test.ts`
> - Удалены `analyze-flow.spec.ts`, `predict-flow.spec.ts`

---

## 4. Unit-тесты — утилиты TypeScript (vitest)

**Расположение:** `tests/ts/`
**Конфигурация:** `vitest.config.ts`

---

### 4.1 `rateLimit()` — `src/lib/rate-limit.ts`

**Файл:** `tests/ts/rate-limit.test.ts`
**Мокинг:** `vi.resetModules()` между тестами для сброса in-memory Map.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Первый запрос разрешён | `rateLimit("k", 5, 60000)` | `allowed === true`, `remaining === 4` | P0 |
| 2 | Лимит превышен | 6 вызовов с max=5 | 6-й: `allowed === false`, `remaining === 0` | P0 |
| 3 | Eviction при >500 ключей | 501 уникальных ключей | Старые ключи удалены, новые работают | P0 |
| 4 | Сброс после windowMs | Вызов после истечения окна | Счётчик обнуляется, `allowed === true` | P0 |
| 5 | Разные ключи не влияют друг на друга | 2 разных ключа | Каждый имеет свой лимит | P1 |

**Граничные случаи:** windowMs=0, maxRequests=1, очень длинный ключ.

```typescript
// tests/ts/rate-limit.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('rateLimit', () => {
  beforeEach(() => { vi.resetModules() })

  it('разрешает первый запрос', async () => {
    const { rateLimit } = await import('@/lib/rate-limit')
    const result = rateLimit('test-key', 3, 60_000)
    expect(result.allowed).toBe(true)
    expect(result.remaining).toBe(2)
  })

  it('отклоняет при превышении лимита', async () => {
    const { rateLimit } = await import('@/lib/rate-limit')
    rateLimit('k', 2, 60_000)
    rateLimit('k', 2, 60_000)
    const result = rateLimit('k', 2, 60_000)
    expect(result.allowed).toBe(false)
    expect(result.remaining).toBe(0)
  })

  it('разные ключи независимы', async () => {
    const { rateLimit } = await import('@/lib/rate-limit')
    rateLimit('a', 1, 60_000)
    const b = rateLimit('b', 1, 60_000)
    expect(b.allowed).toBe(true)
  })
})
```

---

### 4.2 `safeParseStdout()` — `src/lib/api-utils.ts`

**Файл:** `tests/ts/safe-parse-stdout.test.ts`
**Мокинг:** не требуется (чистая функция).

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Валидный JSON-объект | `'{"status":"ok"}'` | `{ data: { status: "ok" } }` | P0 |
| 2 | Валидный JSON-массив | `'[1,2,3]'` | `{ data: [1,2,3] }` | P0 |
| 3 | Невалидный JSON | `'{bad}'` | `{ error: ... }` содержит "Failed to parse" | P0 |
| 4 | Пустой вывод | `''` | `{ error: ... }` содержит "empty output" | P0 |
| 5 | Не-JSON начало (текст) | `'Traceback (most recent)...'` | `{ error: ... }` содержит "non-JSON" | P0 |
| 6 | null stdout | `null` | `{ error: ... }` | P0 |

---

### 4.3 `validateGameId()` — `src/lib/api-utils.ts`

**Файл:** `tests/ts/validate-game-id.test.ts`
**Мокинг:** `vi.spyOn(console, 'warn')` для проверки предупреждений.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Валидный ID из KNOWN_GAMES | `'4x20'` | `null` (без ошибки) | P0 |
| 2 | Пустая строка | `''` | Строка ошибки | P0 |
| 3 | Слишком длинная (>50 символов) | `'a'.repeat(51)` | Строка ошибки | P0 |
| 4 | Недопустимые символы (пробел) | `'4x 20'` | Строка ошибки | P0 |
| 5 | Спецсимволы | `'../etc/passwd'` | Строка ошибки (path traversal) | P0 |
| 6 | Неизвестная игра (без предупреждения) | `'newgame123'` | `null` (допустимый ID) | P0 |

---

### 4.4 `validateFilePath()` — `src/lib/api-utils.ts`

**Файл:** `tests/ts/validate-file-path.test.ts`
**Мокинг:** нет (работает с константами).

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Путь внутри DATA_DIR | `DATA_DIR + "/draws_4x20.txt"` | `null` | P0 |
| 2 | Путь в /tmp/ | `'/tmp/somefile.txt'` | `null` | P0 |
| 3 | Path traversal | `'/etc/passwd'` | Строка ошибки | P0 |
| 4 | Обход через `..` | `DATA_DIR + "/../../etc/passwd"` | Строка ошибки (после resolve) | P0 |
| 5 | Пустая строка | `''` | Строка ошибки | P0 |

---

### 4.5 `countDrawsInFile()` — `src/lib/api-utils.ts`

**Файл:** `tests/ts/count-draws.test.ts`
**Мокинг:** `vi.mock('fs', ...)` — readFileSync, existsSync.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Существующий файл с тиражами | Файл с 10 строками `||` | Возвращает 10 | P0 |
| 2 | Несуществующий файл | `'/nonexistent/path.txt'` | Возвращает 0 | P0 |
| 3 | Кэширование | Второй вызов за <5 мин | Не вызывает readFileSync повторно | P0 |

---

### 4.6 `safeJsonFetch()` — `src/lib/fetch.ts`

**Файл:** `tests/ts/safe-json-fetch.test.ts`
**Мокинг:** `vi.stubGlobal('fetch', mockFn)`.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Успешный 200 + JSON | `{ ok: true, json: {...} }` | `{ data: {...}, ok: true }` | P0 |
| 2 | HTTP 500 | `{ ok: false, status: 500 }` | `{ data: { error: "..." }, ok: false }` | P0 |
| 3 | Таймаут | `DOMException('Timeout')` | `{ data: { error: ... }, ok: false }` | P0 |
| 4 | HTML вместо JSON | `content-type: text/html` | `{ data: { error: ... }, ok: false }` | P0 |
| 5 | Сетевая ошибка | `TypeError: Failed to fetch` | `{ data: { error: ... }, ok: false }` | P0 |
| 6 | Некорректный JSON в теле | JSON.parse бросает исключение | `{ data: { error: ... }, ok: false }` | P1 |

```typescript
import { describe, it, expect, vi } from 'vitest'
import { safeJsonFetch } from '@/lib/fetch'

describe('safeJsonFetch', () => {
  it('успешный JSON ответ', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ result: 'ok' }),
    })
    const r = await safeJsonFetch('/api/test')
    expect(r.ok).toBe(true)
    expect(r.data).toEqual({ result: 'ok' })
  })

  it('HTML ответ', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'text/html' }),
      text: () => Promise.resolve('<html>error</html>'),
    })
    const r = await safeJsonFetch('/api/test')
    expect(r.ok).toBe(false)
  })

  it('таймаут', async () => {
    global.fetch = vi.fn().mockRejectedValue(
      new DOMException('Timeout', 'TimeoutError')
    )
    const r = await safeJsonFetch('/api/test', undefined, 100)
    expect(r.ok).toBe(false)
  })
})
```

---

### 4.7 `adaptPredictResult()` — `src/lib/adapters.ts`

**Файл:** `tests/ts/adapt-predict.test.ts`
**Мокинг:** не требуется (чистая функция маппинга).

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Полные данные | Mock predict JSON со всеми полями | Все типизированные поля корректно смапплены | P0 |
| 2 | Отсутствующие опциональные поля | Без backtest, monte_carlo, cross_validation | Fallback на пустые объекты/массивы | P0 |
| 3 | Consensus votes | С `consensus_votes_b1` | `result.consensusVotesB1` — Record<string, number> | P0 |
| 4 | Frequency analysis | С `frequency_analysis` | `result.frequencyAnalysis` — объект с block1/block2 | P1 |
| 5 | Пустой prediction block | `prediction: { block1: [], block2: [] }` | Без ошибки, пустые массивы | P1 |

---

### 4.8 `adaptPipelineResult()` — `src/lib/adapters.ts`

**Файл:** `tests/ts/adapt-pipeline.test.ts`
**Мокинг:** не требуется.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Полные данные | Mock pipeline JSON | `game_key`, `confidence.overall` — корректные типы | P0 |
| 2 | Fallback game key | Пустое поле `game` | Используется `fallbackGameKey` | P0 |
| 3 | number_spectrum | С `number_spectrum` | Присутствует в результате | P0 |
| 4 | top3_models | С `top3_models` | Массив длиной ≤3 | P0 |
| 5 | Пустой raw | `{}` | Без ошибки, fallback-значения | P1 |

---

### 4.9 `resolvePythonPath()` — `src/lib/python-runner.ts`

**Файл:** `tests/ts/python-runner.test.ts`
**Мокинг:** `vi.mock('child_process')`, `vi.mock('fs')`.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Python найден в venv | existsSync возвращает true, testPython — OK | Возвращает путь к venv python | P0 |
| 2 | Python не найден | Все кандидаты не существуют | Возвращает fallback (`python3`/`python`) | P0 |
| 3 | Мемоизация | Второй вызов | Не проверяет файлы повторно | P0 |

---

### 4.10 `runPythonScript()` — `src/lib/python-runner.ts`

**Файл:** `tests/ts/python-runner.test.ts`
**Мокинг:** `vi.mock('child_process')` — мок spawn.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Скрипт существует и отрабатывает | Мок stdout `'{"ok":1}'` | `{ stdout, stderr, code: 0 }` | P0 |
| 2 | Скрипт не найден | `existsSync` возвращает false | Reject с `Error('Python script not found...')` | P0 |
| 3 | Таймаут | Таймер убивает процесс | `{ code: null }` (SIGKILL) | P0 |

---

### 4.11 `createCachedOperationHandler()` — `src/lib/background-cache.ts`

**Файл:** `tests/ts/background-cache.test.ts`
**Мокинг:** `vi.mock('@/lib/python-runner')`, `vi.mock('@/lib/api-utils')`, `vi.mock('@/lib/rate-limit')`, `vi.mock('fs')`.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Кэш-попадание | Первый запрос → фоновое выполнение → второй → из кэша | Второй: `_cached: true` | P0 |
| 2 | Rate limit | Превышен лимит | HTTP 429 с `retry_after` | P0 |
| 3 | Невалидный game ID | Пустой game | HTTP 400 | P0 |
| 4 | Файл не найден | `existsSync` → false | HTTP 400 с hint | P0 |
| 5 | Фоновое выполнение успешно | runPythonScript возвращает JSON | Кэш заполнен, `_refreshing: false` | P0 |
| 6 | Фоновое выполнение с ошибкой | runPythonScript возвращает code=1 | Кэш содержит `{ status: 'error' }` | P0 |

---

### 4.12 `utils.ts` — `src/lib/utils.ts`

**Файл:** `tests/ts/utils.test.ts`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | `cn()` — слияние классов | `'foo', 'bar'` | `'foo bar'` | P0 |
| 2 | `cn()` — условные классы | `condition && 'active'` | Правильное слияние/исключение | P0 |

---

## 5. Unit-тесты — React-хуки (vitest)

### 5.1 `usePolling` — `src/hooks/usePolling.ts`

**Файл:** `tests/hooks/use-polling.test.ts`
**Мокинг:** `vi.useFakeTimers()`, `@testing-library/react` renderHook.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Max retries | `maxRetries: 3, delayMs: 100` | pollFn вызван ≤3 раз | P1 |
| 2 | Отмена через versionRef | Инкремент versionRef | Новые вызовы pollFn прекращаются | P1 |
| 3 | onError при сетевой ошибке | pollFn бросает reject | onError вызван с ошибкой | P1 |
| 4 | Успешное завершение | pollFn возвращает true | Поллинг останавливается, вызван onSuccess (если есть) | P1 |

```typescript
import { renderHook, act } from '@testing-library/react'
import { usePolling } from '@/hooks/usePolling'

describe('usePolling', () => {
  it('останавливается после maxRetries', async () => {
    vi.useFakeTimers()
    const pollFn = vi.fn().mockResolvedValue(true)
    const { result } = renderHook(() =>
      usePolling({ maxRetries: 3, delayMs: 100 })
    )
    act(() => result.current.startPolling(pollFn))
    await act(async () => { vi.advanceTimersByTime(1500) })
    expect(pollFn.mock.calls.length).toBeLessThanOrEqual(3)
    vi.useRealTimers()
  })

  it('отменяется при изменении versionRef', async () => {
    vi.useFakeTimers()
    const pollFn = vi.fn().mockResolvedValue(true)
    const { result } = renderHook(() =>
      usePolling({ maxRetries: 100, delayMs: 100 })
    )
    act(() => result.current.startPolling(pollFn))
    act(() => { result.current.versionRef.current++ })
    await act(async () => { vi.advanceTimersByTime(2000) })
    const callsAfterCancel = pollFn.mock.calls.length
    await act(async () => { vi.advanceTimersByTime(2000) })
    expect(pollFn.mock.calls.length).toBe(callsAfterCancel)
    vi.useRealTimers()
  })
})
```

---

### 5.2 `usePrefersReducedMotion` — `src/hooks/usePrefersReducedMotion.ts`

**Файл:** `tests/hooks/use-prefers-reduced-motion.test.ts`
**Мокинг:** `window.matchMedia`, `useSyncExternalStore`.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | По умолчанию — motion включён | `matches: false` | Возвращает `false` | P1 |
| 2 | Пользователь включил reduced-motion | `matches: true` | Возвращает `true` | P1 |
| 3 | Изменение в рантайме | `change` событие | Хук обновляет значение | P1 |
| 4 | SSR / server snapshot | `typeof window === 'undefined'` | Возвращает `false` | P1 |

```typescript
import { renderHook } from '@testing-library/react'

describe('usePrefersReducedMotion', () => {
  it('возвращает false когда motion включён', () => {
    const mq = { matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }
    window.matchMedia = vi.fn().mockReturnValue(mq)
    const { result } = renderHook(() => usePrefersReducedMotion())
    expect(result.current).toBe(false)
  })

  it('возвращает true когда reduced-motion включён', () => {
    const mq = { matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }
    window.matchMedia = vi.fn().mockReturnValue(mq)
    const { result } = renderHook(() => usePrefersReducedMotion())
    expect(result.current).toBe(true)
  })
})
```

---

## 6. Компонентные тесты (React Testing Library)

**Расположение:** `tests/components/`
**Инструмент:** `@testing-library/react` + `vitest`

---

### 6.1 `types.ts` — типы и константы

**Файл:** `tests/components/types.test.ts`
**Мокинг:** не требуется.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | GAME_FORMATS содержит все ключи | — | `'4x20'`, `'6x45plus'`, `'5x36plus'`, `'keno2'` ∈ GAME_FORMATS | P0 |
| 2 | BLOCK_COLOR_CLASSES содержит blue и emerald | — | Классы содержат полный `bg-`, `text-`, `border-` | P0 |

---

### 6.2 `CopyButton` — `src/components/lottery/CopyButton.tsx`

**Файл:** `tests/components/CopyButton.test.tsx`
**Мокинг:** `navigator.clipboard.writeText`.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Копирует текст | `text="1,2,3,4"` | `writeText` вызван с `"1,2,3,4"` | P1 |
| 2 | Показывает успех | После копирования | Иконка Check (emerald) отображается | P1 |
| 3 | Сброс через 1.5с | Таймер | Возвращается к иконке Copy | P1 |

---

### 6.3 `StepIndicator` — `src/components/lottery/StepIndicator.tsx`

**Файл:** `tests/components/StepIndicator.test.tsx`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Рендерит 4 вкладки | `step=1, selectedGame=null` | В DOM: вкладки «Анализ», «Тиражи», «Прогноз», «Pipeline» | P1 |
| 2 | ARIA-атрибуты | — | `role="tablist"`, `aria-selected` на активной, `aria-controls` | P1 |
| 3 | Шаг 2 disabled без игры | `selectedGame=null` | Кнопка «Тиражи» — disabled | P1 |
| 4 | Шаг 2 enabled с игрой | `selectedGame={mockGame}` | Кнопка «Тиражи» — не disabled | P1 |
| 5 | Шаг 4 disabled без прогноза | `predictResult=null` | Кнопка «Pipeline» — disabled | P1 |

```tsx
import { render, screen } from '@testing-library/react'
import { StepIndicator } from '@/components/lottery/StepIndicator'
import type { GameAnalysis } from '@/components/lottery/types'

const mockGame: GameAnalysis = {
  name: '4x20', key: '4x20', score: 10, verdict: 'ok',
  verdict_color: 'green', draws: 100, hot_numbers: [], cold_numbers: [],
  chi2_p: null, autocorr: null,
}

describe('StepIndicator', () => {
  it('рендерит 4 вкладки', () => {
    render(<StepIndicator step={1} setStep={() => {}} selectedGame={null} fetchDone={false} predictResult={null} />)
    expect(screen.getByRole('tab', { name: /Анализ/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Тиражи/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Прогноз/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Pipeline/i })).toBeInTheDocument()
  })

  it('шаг 2 disabled без выбранной игры', () => {
    render(<StepIndicator step={1} setStep={() => {}} selectedGame={null} fetchDone={false} predictResult={null} />)
    expect(screen.getByRole('tab', { name: /Тиражи/i })).toBeDisabled()
  })
})
```

---

### 6.4 `Step1Analysis` — `src/components/lottery/Step1Analysis.tsx`

**Файл:** `tests/components/Step1Analysis.test.tsx`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Loading skeleton | `loading=true` | Skeleton-компоненты отображаются | P1 |
| 2 | Error state | `error="Ошибка сети"` | Сообщение об ошибке в DOM | P1 |
| 3 | Список игр | Массив GameAnalysis | Названия игр отображаются | P1 |
| 4 | High anomaly cards | Игры с score > 50 | Карточки с цветной рамкой и verdict | P1 |
| 5 | Клик по игре вызывает onSelect | Нажатие на карточку | `onSelect` вызван с объектом GameAnalysis | P1 |

---

### 6.5 `Step2Draws` — `src/components/lottery/Step2Draws.tsx`

**Файл:** `tests/components/Step2Draws.test.tsx`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Информация об игре | `selectedGame` | Название игры, формат, кол-во тиражей | P1 |
| 2 | Внешняя ссылка на stoloto.ru | `selectedGame.key` | Ссылка `stoloto.ru/{key}/archive` с `target="_blank"` | P1 |
| 3 | Кнопка загрузки | — | Кнопка «Загрузить все тиражи» вызывает `onFetchDraws` | P1 |
| 4 | Результат загрузки | `totalDraws > 0` | Отображается количество загруженных тиражей | P1 |

---

### 6.6 `Step3Predict` — `src/components/lottery/Step3Predict.tsx`

**Файл:** `tests/components/Step3Predict.test.tsx`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Отображение предсказания | `prediction.block1=[1,2,3,4]` | Числа отображаются в UI | P1 |
| 2 | Backtest heatmap | `backtest.heatmap.length > 0` | HeatmapRow-компоненты рендерятся | P1 |
| 3 | Monte Carlo | `monte_carlo` данные | Карточка Monte Carlo отображается | P1 |
| 4 | Топ-5 моделей | `top5_models` данные | Карточка «Топ-5 лучших моделей» | P1 |
| 5 | Пары и gaps | `pair_analysis`, `gap_analysis` | Карточки с парами и просроченными числами | P1 |

---

### 6.7 `Step4Pipeline` — `src/components/lottery/Step4Pipeline.tsx`

**Файл:** `tests/components/Step4Pipeline.test.tsx`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Pipeline-результат | `pipelineResult` | Confidence.overall отображается | P1 |
| 2 | Позиционный анализ | `block1_position` | Карточка позиционного анализа | P1 |
| 3 | Частотный анализ | `block2_frequency` | Карточка частотного анализа | P1 |
| 4 | Сравнение | `std_prediction` + `rng_prediction` | Обе карточки рендерятся | P1 |

---

### 6.8 `HeatmapRow` — `src/components/lottery/HeatmapRow.tsx`

**Файл:** `tests/components/HeatmapRow.test.tsx`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Expand/collapse | Клик на строку | Детали появляются, повторный клик — скрываются | P1 |
| 2 | Подсветка попаданий | Совпадающие числа | Числа с классом `bg-emerald-500/40` | P1 |
| 3 | Лучший модель | `bestModel={{ name: 'm01_freq' }}` | Имя модели отображается | P1 |
| 4 | aria-expanded | — | Кнопка имеет `aria-expanded` true/false | P1 |
| 5 | null-safe act_b1/pred_b1 | `act_b1=null` | Без краша, числа не отображаются | P0 |

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { HeatmapRow } from '@/components/lottery/HeatmapRow'

const mockEntry = {
  draw_no: 100, pred_b1: [1, 2, 3, 4], pred_b2: [5, 6, 7, 8],
  act_b1: [1, 3, 5, 7], act_b2: [6, 8, 9, 10],
  hits_b1: 2, hits_b2: 2, total: 4, date: '01.01.2024',
}

describe('HeatmapRow', () => {
  it('expand/collapse работает', () => {
    render(<HeatmapRow entry={mockEntry} bgColor="bg-white/5" />)
    const btn = screen.getByRole('button', { expanded: false })
    fireEvent.click(btn)
    expect(screen.getByText(/Блок 1/i)).toBeInTheDocument()
  })

  it('null-safe при отсутствии act_b1', () => {
    const entry = { ...mockEntry, act_b1: null }
    expect(() => render(<HeatmapRow entry={entry} bgColor="bg-white/5" />)).not.toThrow()
  })
})
```

---

## 7. Тестирование ErrorBoundary

**Файл:** `tests/components/ErrorBoundary.test.tsx`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Нормальный рендеринг | `children=<div>OK</div>` | Дочерний элемент отображается | P1 |
| 2 | Перехват ошибки | Компонент-потомок бросает error | UI с «Что-то пошло не так» | P1 |
| 3 | Кастомный fallback | `fallback=<div>Fallback</div>` | Fallback отображается вместо стандартного | P1 |

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorBoundary } from '@/components/ErrorBoundary'

function ThrowOnRender() {
  throw new Error('test error')
}

describe('ErrorBoundary', () => {
  // Подавить React error logging в тестах
  const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

  it('перехватывает ошибку и показывает UI', () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender />
      </ErrorBoundary>
    )
    expect(screen.getByText(/Что-то пошло не так/i)).toBeInTheDocument()
  })

  it('сбрасывает ошибку при нажатии кнопки', () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender />
      </ErrorBoundary>
    )
    fireEvent.click(screen.getByRole('button', { name: /Попробовать снова/i }))
    // После сброса — повторная ошибка (так как ThrowOnRender всё ещё бросает)
    expect(screen.getByText(/Что-то пошло не так/i)).toBeInTheDocument()
  })
})
```

---

## 8. Интеграционные тесты — API-маршруты

**Расположение:** `tests/integration/`
**Инструмент:** vitest + мок `child_process` (Python не вызывается)

### Стратегия мокирования

- `runPythonScript` → мок через `vi.mock('@/lib/python-runner')`
- Файловая система → мок через `vi.mock('fs')`
- Rate limiter → `vi.mock('@/lib/rate-limit')`

---

### 8.1 API Routes Contract — параметризованная проверка 4 маршрутов

**Файл:** `tests/integration/api-routes-contract.test.ts`
**Стратегия:** Общий шаблон тестирования для маршрутов `/api/lottery/analyze`, `/api/lottery/fetch-draws`, `/api/lottery/predict`, `/api/lottery/pipeline`. Каждый маршрут проверяется по одному и тому же набору паттернов.

| # | Тест-кейс | Маршрут | Ожидание | Приоритет |
|---|-----------|---------|----------|-----------|
| 1 | Фоновое выполнение | analyze, fetch-draws, predict, pipeline | Первый запрос: `_refreshing: true` или `status: "pending"` | P0 |
| 2 | Кэш-попадание | analyze, fetch-draws, predict, pipeline | После выполнения: `_cached: true` | P0 |
| 3 | Файл / данные не найдены | analyze, fetch-draws, predict, pipeline | HTTP 400 с подсказкой или `_refreshing: true` | P0 |
| 4 | Ошибка Python | analyze, predict | runPythonScript code=1 → 200 с `{ error: "..." }` | P0 |
| 5 | Rate limiting | fetch-draws, predict | Превышение лимита → 429 | P0 |
| 6 | Валидация game ID | fetch-draws, predict | Невалидный game → 400 | P0 |
| 7 | Валидация пустого game | analyze, fetch-draws | Пустой game → 400 | P0 |
| 8 | Кэш-first при наличии файла | fetch-draws | existsSync → true → 200 с данными | P0 |
| 9 | JSON-ответ (структура) | analyze | Status 200, `body.games` — массив | P0 |
| 10 | Кэширование двух запросов подряд | analyze | Второй POST → `_cached: true` | P0 |

> **Консолидация v3.0:** Секции 7.1–7.4 (18 тестов, 4 файла) объединены в один параметризованный файл `api-routes-contract.test.ts` (~10 тестов). Это устраняет дублирование общего мокинга и проверяет единый контракт API-маршрутов.

```typescript
// tests/integration/api-routes-contract.test.ts
import { describe, it, expect, vi, beforeAll } from 'vitest'

const ROUTES = [
  { name: 'analyze', path: '/api/lottery/analyze', method: 'POST' },
  { name: 'fetch-draws', path: '/api/lottery/fetch-draws', method: 'POST' },
  { name: 'predict', path: '/api/lottery/predict', method: 'POST' },
  { name: 'pipeline', path: '/api/lottery/pipeline', method: 'POST' },
]

describe.each(ROUTES)('API Contract: $name', ({ name, path, method }) => {
  it('фоновое выполнение — первый запрос возвращает refreshing', async () => {
    const res = await fetch(`http://localhost${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game: '4x20' }),
    })
    expect(res.status).toBe(200)
    const data = await res.json()
    expect(data._refreshing || data.status).toBeDefined()
  })

  it('кэш-попадание — второй запрос возвращает cached', async () => {
    // Первый запрос для заполнения кэша
    await fetch(`http://localhost${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game: '4x20' }),
    })
    // Второй запрос
    const res = await fetch(`http://localhost${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game: '4x20' }),
    })
    const data = await res.json()
    expect(data._cached).toBe(true)
  })

  it('невалидный game ID → 400', async () => {
    const res = await fetch(`http://localhost${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game: 'invalid name!' }),
    })
    expect(res.status).toBe(400)
  })
})
```

---

### 8.2 `GET /api/download-project`

**Файл:** `tests/integration/api-download-project.test.ts`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Возвращает tar.gz | GET | Status 200, `content-type` содержит `application/gzip` | P1 |

---

### 8.3 Полный поток: analyze → fetch-draws → predict → pipeline

**Файл:** `tests/integration/full-flow.test.ts`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Последовательность API | Мок всех 4 маршрутов | analyze → массив games → fetch → total_draws → predict → prediction → pipeline → pipeline result | P0 |
| 2 | Ошибка на любом шаге | predict возвращает error | Error-состояние корректно обрабатывается на фронтенде | P0 |

---

## 9. E2E-тесты — полный мастер

**Расположение:** `tests/e2e/`
**Инструмент:** Playwright

### Стратегия

E2E-тесты запускаются против **реального dev-сервера** (`next dev`) с **мокированным Python-бэкендом**. Python-скрипты подменяются на заглушки, возвращающие предсказуемый JSON.

> **Консолидация v3.0:** Секции «Анализ игр» и «Предсказание» (Шаги 1–3) удалены. Все проверки покрываются одним полным мастер-тестом, что исключает дублирование и сокращает время E2E в 4 раза.

---

### 9.1 Полный мастер (Шаги 1–4)

**Файл:** `tests/e2e/full-wizard.spec.ts`

| # | Тест-кейс | Действия | Ожидание | Приоритет |
|---|-----------|----------|----------|-----------|
| 1 | Полный поток | Анализ → выбор игры → загрузка → прогноз → pipeline | Все 4 шага пройдены, данные отображаются | P0 |
| 2 | Навигация клавиатурой | Tab / Enter / стрелки | Все шаги доступны с клавиатуры | P1 |
| 3 | Кнопка «Назад» | Вернуться с шага 3 на шаг 2 | Данные шага 2 сохранены | P1 |

---

## 10. Unit-тесты — Python (pytest)

**Расположение:** `tests/python/`
**Фикстуры:** `tests/python/conftest.py`

### Общие fixture'ы (conftest.py)

```python
# tests/python/conftest.py
import pytest
from dataclasses import dataclass
from typing import List

@dataclass
class Draw:
    date: str
    number: int
    block1: List[int]
    block2: List[int]

@pytest.fixture
def make_draws():
    """Фабрика для генерации Draw-объектов."""
    def _make(count: int, b1_size: int = 4, b2_size: int = 4,
              b1_max: int = 20, b2_max: int = 20) -> List[Draw]:
        draws = []
        for i in range(count):
            b1 = list(range(1, b1_size + 1))
            b2 = list(range(1, b2_size + 1))
            draws.append(Draw(
                date=f"01.01.2024",
                number=i + 1,
                block1=b1,
                block2=b2,
            ))
        return draws
    return _make

@pytest.fixture
def sample_draws_4x20(make_draws):
    return make_draws(50, b1_size=4, b2_size=4, b1_max=20, b2_max=20)

@pytest.fixture(autouse=True)
def _reset_globals():
    """Сбросить глобальные PICK_B1/PICK_B2 перед каждым тестом."""
    import lp_v130_app
    original_b1 = lp_v130_app.PICK_B1
    original_b2 = lp_v130_app.PICK_B2
    original_b1max = lp_v130_app.B1_MAX
    original_b2max = lp_v130_app.B2_MAX
    yield
    lp_v130_app.PICK_B1 = original_b1
    lp_v130_app.PICK_B2 = original_b2
    lp_v130_app.B1_MAX = original_b1max
    lp_v130_app.B2_MAX = original_b2max
```

---

### 10.1 `parse_line()` — `python/lp_v130_app.py`

**Файл:** `tests/python/test_parse_line.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Валидная 3-частная строка | `"01.01.2024 12:00\|\|100\|\|1,2,3,4"` | `Draw(block1=[1,2,3,4], block2=[])` | P0 |
| 2 | Валидная 4-частная строка | `"... \|\| 1,2,3,4 \|\| 5,6,7,8"` | `Draw(block1=[1,2,3,4], block2=[5,6,7,8])` | P0 |
| 3 | 5-частная (extra-поле) | `"... \|\| 1,2,3,4 \|\| 5,6,7,8 \|\| extra"` | Extra игнорируется | P0 |
| 4 | Пустая строка | `""` | `None` | P0 |
| 5 | Невалидный формат | `"no-pipes"` | `None` | P0 |
| 6 | Менее 2 чисел в блоке | `"... \|\| 5"` | `None` | P0 |
| 7 | Отрицательное число | `"... \|\| -1,2,3,4"` | `None` | P0 |

```python
class TestParseLine:
    def test_valid_3part(self):
        from lp_v130_app import parse_line
        d = parse_line("01.01.2024 12:00||100||1,2,3,4")
        assert d is not None
        assert d.block1 == [1, 2, 3, 4]
        assert d.block2 == []

    def test_valid_4part(self):
        from lp_v130_app import parse_line
        d = parse_line("01.01.2024 12:00||100||1,2,3,4||5,6,7,8")
        assert d.block1 == [1, 2, 3, 4]
        assert d.block2 == [5, 6, 7, 8]

    def test_empty_string(self):
        from lp_v130_app import parse_line
        assert parse_line("") is None

    def test_negative_number(self):
        from lp_v130_app import parse_line
        assert parse_line("01.01.2024||1||-1,2,3,4") is None
```

---

### 10.2 `parse_text()` — `python/lp_v130_app.py`

**Файл:** `tests/python/test_parse_text.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | С game hint (4x20) | text + game_name="4x20" | `PICK_B1=4, PICK_B2=4` из hints | P0 |
| 2 | Без game hint | text без game_name | Авто-детекция PICK из моды | P0 |
| 3 | Дубликаты тиражей | Повторяющиеся строки | Дубли удалены, лог с предупреждением | P0 |
| 4 | Отклонённые строки | Невалидные строки | `rejected > 0` | P0 |
| 5 | Пустой текст | `""` | Пустой список без ошибок | P0 |

---

### 10.3 `GAME_FORMAT_HINTS` — `python/lp_v130_app.py`

**Файл:** `tests/python/test_game_hints.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Все записи валидны | — | Каждая содержит `pick_b1`, `pick_b2`, `b1_max`, `b2_max`; `b1_max >= pick_b1` | P0 |
| 2 | Известные игры присутствуют | — | `'4x20'`, `'6x45plus'`, `'5x36plus'`, `'5x2'`, `'keno2'` ∈ hints | P0 |

---

### 10.4 `b1b2_from_scores()` — `python/lp_v130_app.py`

**Файл:** `tests/python/test_b1b2_from_scores.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Корректное количество | scores dict | `len(b1) == PICK_B1`, `len(b2) == PICK_B2` | P0 |
| 2 | Без дубликатов | — | `len(set(b1)) == len(b1)`, `len(set(b2)) == len(b2)` | P0 |
| 3 | Диапазон чисел | — | `1 <= x <= b1_max` для всех x ∈ b1 | P0 |

---

### 10.5 `FreqCache` — `python/lp_v130_app.py`

**Файл:** `tests/python/test_freq_cache.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | gap1 для свежего числа | Последний тираж содержит число N | `gap1(N) == 0` | P0 |
| 2 | gap1 для отсутствующего | Число 999 не выпадало | `gap1(999) == len(draws)` | P0 |
| 3 | last_seen | — | `ls1[x]` = индекс последнего появления | P0 |
| 4 | aff() block affinity | 100% в block1 | `aff(N) == 1.0` | P0 |

---

### 10.6 `exp_w()` — `python/lp_v130_app.py`

**Файл:** `tests/python/test_exp_w.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | exp_w(0) == 1.0 | — | Свежий элемент: вес 1.0 | P0 |
| 2 | Монотонное убывание | exp_w(0), exp_w(10), exp_w(100) | `exp_w(0) > exp_w(10) > exp_w(100)` | P0 |

---

### 10.7 Predict helpers — `python/predict.py`

**Файл:** `tests/python/test_predict_helpers.py`
**Консолидация v3.0:** Объединены `test_pair_analysis.py`, `test_gap_analysis.py`, `test_sum_range.py`, `test_cross_game.py`, `test_consensus.py` → один файл с параметризованными тестами.

| # | Тест-кейс | Модуль | Вход | Ожидание | Приоритет |
|---|-----------|--------|------|----------|-----------|
| 1 | Подсчёт пар | `build_pair_analysis` | Пара (1,2) встречается 3 раза | `count = 3` в результате | P1 |
| 2 | Мало тиражей для пар | `build_pair_analysis` | 5 тиражей | Пустой список | P1 |
| 3 | Просроченные числа | `build_gap_analysis` | Число с gap > avg_gap | `overdue_score > 0` | P1 |
| 4 | Пустые draws для gaps | `build_gap_analysis` | `[]` | `{"block1": [], "block2": []}` | P1 |
| 5 | mean/std корректны | `build_sum_range_stats` | 50 тиражей | `stats["block1"]["mean"]` ≈ среднее сумм | P1 |

```python
# tests/python/test_predict_helpers.py
"""Консолидированные тесты helpers predict.py: pair, gap, sum_range, cross_game, consensus."""
import pytest

class TestPredictHelpers:

    # --- build_pair_analysis ---
    def test_pair_count(self, sample_draws_4x20):
        from predict import build_pair_analysis
        result = build_pair_analysis(sample_draws_4x20, pick=4)
        assert isinstance(result, list)

    def test_pair_few_draws(self):
        from predict import build_pair_analysis
        # Мало тиражей → пустой список
        result = build_pair_analysis([], pick=4)
        assert result == []

    # --- build_gap_analysis ---
    def test_gap_overdue(self, sample_draws_4x20):
        from predict import build_gap_analysis
        result = build_gap_analysis(sample_draws_4x20, pick=4)
        assert "block1" in result

    def test_gap_empty_draws(self):
        from predict import build_gap_analysis
        result = build_gap_analysis([], pick=4)
        assert result == {"block1": [], "block2": []}

    # --- build_sum_range_stats ---
    def test_sum_range_mean(self, sample_draws_4x20):
        from predict import build_sum_range_stats
        stats = build_sum_range_stats(sample_draws_4x20)
        assert "block1" in stats
        assert "mean" in stats["block1"]

    # --- build_cross_game_analysis ---
    def test_cross_game_hot(self, tmp_path):
        from predict import build_cross_game_analysis
        result = build_cross_game_analysis("4x20", data_dir=str(tmp_path))
        assert isinstance(result, dict)
```

---

### 10.8 Predict analysis — `python/predict.py`

**Файл:** `tests/python/test_predict_analysis.py`
**Консолидация v3.0:** Объединены `test_frequency.py`, `test_heatmap.py`, `test_top5.py`, `test_time_weights.py` → один файл с параметризованными тестами.

| # | Тест-кейс | Модуль | Вход | Ожидание | Приоритет |
|---|-----------|--------|------|----------|-----------|
| 1 | Частотный подсчёт | `build_frequency_analysis` | 50 тиражей | Каждое число с правильным count | P1 |
| 2 | Пустой draws для frequency | `build_frequency_analysis` | `[]` | `{"block1": [], "block2": []}` | P1 |
| 3 | Подсчёт hits в heatmap | `build_backtest_heatmap` | — | `hits_b1 + hits_b2 = total` | P1 |
| 4 | Ранжирование моделей | `compute_top5_models` | model_report_data | `models[0].score >= models[1].score` | P1 |
| 5 | Последний элемент weight=1.0 | `_compute_time_weights` | n элементов | `weights[-1] == 1.0` | P1 |

```python
# tests/python/test_predict_analysis.py
"""Консолидированные тесты analysis predict.py: frequency, heatmap, top5, time_weights, consensus."""
import pytest

class TestPredictAnalysis:

    # --- build_frequency_analysis ---
    def test_frequency_count(self, sample_draws_4x20):
        from predict import build_frequency_analysis
        result = build_frequency_analysis(sample_draws_4x20, pick=4)
        assert "block1" in result

    def test_frequency_empty(self):
        from predict import build_frequency_analysis
        result = build_frequency_analysis([], pick=4)
        assert result == {"block1": [], "block2": []}

    # --- build_backtest_heatmap ---
    def test_heatmap_hits(self, sample_draws_4x20):
        from predict import build_backtest_heatmap
        result = build_backtest_heatmap(sample_draws_4x20, max_draws=10, pick=4)
        if len(result) > 0:
            entry = result[0]
            assert entry["hits_b1"] + entry["hits_b2"] == entry["total"]

    # --- compute_top5_models ---
    def test_top5_ranking(self, sample_draws_4x20):
        from predict import compute_top5_models
        # Пустые данные → пустой рейтинг
        result = compute_top5_models({})
        assert isinstance(result, list)

    # --- _compute_time_weights ---
    def test_time_weights_last_is_one(self):
        from predict import _compute_time_weights
        weights = _compute_time_weights(50)
        assert weights[-1] == 1.0
```

---

### 10.9 Pipeline: `build_frequency_prediction()` и `build_top3_models()`

**Файл:** `tests/python/test_pipeline_predict.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | frequency_prediction | accuracy_history | `result["block1"]` — list of int | P0 |
| 2 | top3_models | accuracy_history | `len(top3) <= 3` | P0 |

---

### 10.10 Pipeline: `analyze_from_pipeline_data()`

**Файл:** `tests/python/test_pipeline_analyze.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Confidence в диапазоне | — | Все confidence ∈ [0, 1] | P0 |

---

### 10.11 `extract_blocks()` — `python/fetch_draws.py`

**Файл:** `tests/python/test_extract_blocks.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Format A — flat list + hints | `[1,2,3,4,5,6,7,8]`, hint 4x20 | `block1=[1,2,3,4], block2=[5,6,7,8]` | P1 |
| 2 | Format B — dict played/notPlayed | `{"played":[1,2,3,4],"notPlayed":[5]}` | `block1=[1,2,3,4], block2=[5]` | P1 |
| 3 | Format D — list-of-dicts | `[{"first":[1,2],"second":[3,4]}]` | `block1=[1,2], block2=[3,4]` | P1 |
| 4 | Пустой combination | `None` | `("", "")` | P1 |

---

### 10.12 `draw_to_line()` — `python/fetch_draws.py`

**Файл:** `tests/python/test_draw_to_line.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | 4-part output | draw с block1 и block2 | `DATE||NUM||B1||B2` | P1 |
| 2 | 3-part fallback | draw с пустым block2 | `DATE||NUM||ALL` | P1 |

---

### 10.13 `analyze.py` — CLI

**Файл:** `tests/python/test_analyze_cli.py`
**Мокинг:** `unittest.mock.patch('subprocess.run')`.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | `--list-only` флаг | `["--list-only"]` | JSON с game names, без загрузки тиражей | P0 |
| 2 | Обычный запуск | Без флагов | JSON с полным анализом | P1 |

---

### 10.14 `fetch.py` — CLI-обёртка

**Файл:** `tests/python/test_fetch_cli.py`
**Мокинг:** `unittest.mock.patch('subprocess.run')`.

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Успешная загрузка | game="4x20" | JSON с `total_draws > 0`, `data_file` | P0 |
| 2 | Несуществующая игра | game="nonexistent" | JSON с `error`, без краша | P0 |

---

### 10.15 `_validate_written_file()` — `python/fetch_draws.py`

**Файл:** `tests/python/test_validate_written_file.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Корректные строки | Файл с валидными тиражами | Без предупреждений | P1 |
| 2 | Невалидные строки | Строка с не-числами | stderr содержит `[WARN]` | P1 |

---

## 11. Интеграционные Python E2E-тесты

### 11.1 Полный цикл: parse_text → обучение → consensus → prediction

**Файл:** `tests/python/test_e2e_predict.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Полный цикл обучения | 50 тиражей 4x20 | `run_training()` → predictor не None, `last_pred` содержит block1 и block2 | P0 |
| 2 | Prediction содержит блоки | — | `len(block1) == 4`, `len(block2) == 4` | P0 |
| 3 | Consensus agreement | — | `agreement > 0` | P1 |

### 11.2 Pipeline E2E

**Файл:** `tests/python/test_e2e_pipeline.py`

| # | Тест-кейс | Вход | Ожидание | Приоритет |
|---|-----------|------|----------|-----------|
| 1 | Полный pipeline | pipeline_data JSON | `analyze_from_pipeline_data()` → корректный результат | P0 |
| 2 | Circular import check | — | `from pipeline import analyze_from_pipeline_data` — без ImportError | P0 |

---

## 12. Методология проверки покрытия

### 12.1 Целевые показатели

| Метрика | Целевое значение | Минимально допустимое |
|---------|-----------------|----------------------|
| **Line coverage (TS)** | ≥ 85% | ≥ 75% |
| **Line coverage (Python)** | ≥ 80% | ≥ 70% |
| **Branch coverage** | ≥ 70% | ≥ 60% |
| **Function coverage** | ≥ 90% | ≥ 80% |

### 12.2 Инструменты измерения

- **TypeScript:** `vitest --coverage` с `@vitest/coverage-v8`
- **Python:** `pytest --cov=python --cov-report=term-missing --cov-report=html`

### 12.3 Принципы без избыточности

1. **Unit-тесты покрывают логику.** Каждый тест проверяет одну функцию/ветку. Не дублируют интеграционные тесты.
2. **Интеграционные тесты покрывают связывание.** Проверяют, что модули корректно работают вместе. Не проверяют внутреннюю логику модулей (это делают unit-тесты).
3. **E2E-тесты покрывают пользовательские сценарии.** Проверяют полный путь от UI до API до результата. Минимальное количество (3 сценария), только критические пути.
4. **Матрица покрытия по файлам:** каждый файл должен быть затронут хотя бы одним типом теста.

### 12.4 Матрица покрытия «файл → тип теста»

| Файл | Unit | Component | Integration | E2E | Python |
|------|------|-----------|-------------|-----|--------|
| `rate-limit.ts` | ✅ P0 | — | ✅ (опосредованно) | — | — |
| `api-utils.ts` | ✅ P0 | — | ✅ (опосредованно) | — | — |
| `fetch.ts` | ✅ P0 | — | — | — | — |
| `adapters.ts` | ✅ P0 | — | — | — | — |
| `python-runner.ts` | ✅ P0 | — | ✅ (мок) | — | — |
| `background-cache.ts` | ✅ P0 | — | ✅ (мок) | — | — |
| `utils.ts` | ✅ P0 | — | — | — | — |
| `usePolling.ts` | ✅ P1 | — | — | — | — |
| `usePrefersReducedMotion.ts` | ✅ P1 | — | — | — | — |
| `types.ts` | ✅ P0 | — | — | — | — |
| `CopyButton.tsx` | — | ✅ P1 | — | — | — |
| `StepIndicator.tsx` | — | ✅ P1 | — | ✅ P1 | — |
| `Step1Analysis.tsx` | — | ✅ P1 | — | ✅ P0 | — |
| `Step2Draws.tsx` | — | ✅ P1 | — | ✅ P0 | — |
| `Step3Predict.tsx` | — | ✅ P1 | — | ✅ P0 | — |
| `Step4Pipeline.tsx` | — | ✅ P1 | — | ✅ P0 | — |
| `HeatmapRow.tsx` | — | ✅ P1 | — | — | — |
| `ErrorBoundary.tsx` | — | ✅ P1 | — | — | — |
| `page.tsx` | — | — | — | ✅ P0 | — |
| `analyze/route.ts` | — | — | ✅ P0 | ✅ P0 | — |
| `fetch-draws/route.ts` | — | — | ✅ P0 | ✅ P0 | — |
| `predict/route.ts` | — | — | ✅ P0 | ✅ P0 | — |
| `pipeline/route.ts` | — | — | ✅ P0 | ✅ P0 | — |
| `download-project/route.ts` | — | — | ✅ P1 | — | — |
| `lp_v130_app.py` | — | — | — | — | ✅ P0 |
| `predict.py` | — | — | — | — | ✅ P0 |
| `pipeline.py` | — | — | — | — | ✅ P0 |
| `analyze.py` | — | — | — | — | ✅ P1 |
| `fetch.py` | — | — | — | — | ✅ P0 |
| `fetch_draws.py` | — | — | — | — | ✅ P1 |
| `lottery_pipeline.py` | — | — | — | — | ✅ P0 |

### 12.5 Исключения из покрытия

Следующие файлы **не требуют** отдельных тестов:
- `layout.tsx` — содержит только метаданные и провайдеры
- `globals.css` — стили, проверяются визуально
- `db.ts` — обёртка Prisma Client, тестируется через Prisma
- Компоненты `src/components/ui/*` (shadcn/ui) — проверяются upstream
- `worklog.md`, `Caddyfile` — конфигурация
- `stoloto_analyzer_v3.py` — P2-модуль, тесты удалены в v3.0

### 12.6 CI-интеграция

Покрытие проверяется автоматически при каждом PR:

```yaml
# .github/workflows/test.yml (пример)
name: Tests
on: [push, pull_request]
jobs:
  ts-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npx vitest run --coverage
      - name: Check coverage threshold
        run: |
          COVERAGE=$(npx vitest run --coverage --reporter=json 2>/dev/null | jq '.totals.lines.pct')
          if (( $(echo "$COVERAGE < 75" | bc -l) )); then
            echo "Coverage $COVERAGE% is below 75% threshold"
            exit 1
          fi

  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pytest pytest-cov requests numpy scipy
      - run: pytest tests/python/ --cov=python --cov-fail-under=70
```

---

## 13. Сводная таблица тестов

| Категория | Модуль | Кол-во тестов | Приоритет | Оценка LOC |
|-----------|--------|---------------|-----------|------------|
| **Python Unit** | `parse_line()` | 7 | P0 | 65 |
| Python Unit | `parse_text()` | 5 | P0 | 70 |
| Python Unit | `GAME_FORMAT_HINTS` | 2 | P0 | 20 |
| Python Unit | `b1b2_from_scores()` | 3 | P0 | 40 |
| Python Unit | `FreqCache` | 4 | P0 | 45 |
| Python Unit | `exp_w()` | 2 | P0 | 15 |
| Python Unit | Predict helpers (консолидация) | 5 | P1 | 70 |
| Python Unit | Predict analysis (консолидация) | 5 | P1 | 75 |
| Python Unit | Pipeline predict | 2 | P0 | 60 |
| Python Unit | Pipeline analyze | 1 | P0 | 30 |
| Python Unit | `extract_blocks()` | 4 | P1 | 55 |
| Python Unit | `draw_to_line()` | 2 | P1 | 30 |
| Python Unit | `analyze.py` CLI | 2 | P0/P1 | 35 |
| Python Unit | `fetch.py` CLI | 2 | P0 | 35 |
| Python Unit | `_validate_written_file()` | 2 | P1 | 30 |
| **Итого Python Unit** | | **48** | | **~730** |
| **TS Unit** | `rateLimit()` | 5 | P0 | 50 |
| TS Unit | `safeParseStdout()` | 6 | P0 | 35 |
| TS Unit | `validateGameId()` | 6 | P0 | 35 |
| TS Unit | `validateFilePath()` | 5 | P0 | 35 |
| TS Unit | `countDrawsInFile()` | 3 | P0 | 30 |
| TS Unit | `safeJsonFetch()` | 6 | P0 | 60 |
| TS Unit | `adaptPredictResult()` | 5 | P0 | 50 |
| TS Unit | `adaptPipelineResult()` | 5 | P0 | 50 |
| TS Unit | `resolvePythonPath()` | 3 | P0 | 30 |
| TS Unit | `runPythonScript()` | 3 | P0 | 35 |
| TS Unit | `createCachedOperationHandler()` | 6 | P0 | 70 |
| TS Unit | `utils.ts` | 2 | P0 | 15 |
| **Итого TS Unit** | | **55** | | **~515** |
| **Hooks** | `usePolling` | 4 | P1 | 45 |
| Hooks | `usePrefersReducedMotion` | 4 | P1 | 30 |
| **Итого Hooks** | | **8** | | **~75** |
| **Component** | `types.ts` | 2 | P0 | 15 |
| Component | `CopyButton` | 3 | P1 | 30 |
| Component | `StepIndicator` | 5 | P1 | 45 |
| Component | `Step1Analysis` | 5 | P1 | 55 |
| Component | `Step2Draws` | 4 | P1 | 45 |
| Component | `Step3Predict` | 5 | P1 | 60 |
| Component | `Step4Pipeline` | 4 | P1 | 45 |
| Component | `HeatmapRow` | 5 | P1 | 55 |
| **Итого Component** | | **33** | | **~355** |
| **ErrorBoundary** | ErrorBoundary | 3 | P1 | 30 |
| **Итого ErrorBoundary** | | **3** | | **~30** |
| **Integration** | API Routes Contract | 10 | P0 | 190 |
| Integration | API `/download-project` | 1 | P1 | 15 |
| Integration | Полный поток | 2 | P0 | 80 |
| **Итого Integration** | | **13** | | **~280** |
| **Python E2E** | Predict E2E | 3 | P0/P1 | 60 |
| Python E2E | Pipeline E2E | 2 | P0 | 50 |
| **Итого Python E2E** | | **5** | | **~110** |
| **E2E** | Full wizard | 3 | P0/P1 | 55 |
| **Итого E2E** | | **3** | | **~55** |
| **ОБЩИЙ ИТОГ** | | **168** | | **~2150** |

---

## 14. Запуск тестового набора

### 14.1 TypeScript-тесты

```bash
# Все TS-тесты
npx vitest run

# С покрытием
npx vitest run --coverage

# Только unit
npx vitest run tests/ts/ tests/hooks/

# Только компоненты
npx vitest run tests/components/

# Только интеграционные
npx vitest run tests/integration/

# Фильтр по файлу
npx vitest run tests/ts/rate-limit.test.ts

# Watch mode
npx vitest
```

### 14.2 Python-тесты

```bash
# Все Python-тесты
cd /home/z/my-project
PYTHONPATH=python pytest tests/python/ -v

# С покрытием
PYTHONPATH=python pytest tests/python/ --cov=python --cov-report=term-missing --cov-report=html

# Только unit
PYTHONPATH=python pytest tests/python/ -k "not e2e"

# Только E2E
PYTHONPATH=python pytest tests/python/ -k "e2e"

# Конкретный файл
PYTHONPATH=python pytest tests/python/test_parse_line.py -v
```

### 14.3 E2E-тесты

```bash
# Запустить dev-сервер
npx next dev --port 3000 &

# Все E2E-тесты
npx playwright test

# Конкретный файл
npx playwright test tests/e2e/full-wizard.spec.ts

# С UI-режимом
npx playwright test --ui

# Headed (с открытием браузера)
npx playwright test --headed
```

### 14.4 Полный набор (all-in-one)

```bash
#!/bin/bash
# run-all-tests.sh

set -e
echo "=== TypeScript Unit + Component + Integration ==="
npx vitest run --coverage

echo "=== Python Unit + E2E ==="
PYTHONPATH=python pytest tests/python/ --cov=python --cov-report=term-missing

echo "=== E2E (Playwright) ==="
npx playwright test

echo "=== All tests passed ==="
```

---

## 15. Конфигурационные файлы

### 15.1 `vitest.config.ts`

```typescript
import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json-summary'],
      include: [
        'src/lib/**/*.ts',
        'src/hooks/**/*.ts',
        'src/components/lottery/**/*.{ts,tsx}',
        'src/components/ErrorBoundary.tsx',
        'src/app/api/**/*.ts',
      ],
      exclude: [
        'src/components/ui/**',
        'src/lib/db.ts',
      ],
      thresholds: {
        lines: 75,
        functions: 80,
        branches: 60,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

### 15.2 `tests/setup.ts`

```typescript
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// Мок matchMedia для usePrefersReducedMotion
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Мок clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
})
```

### 15.3 `pytest.ini` (или `pyproject.toml`)

```ini
[pytest]
testpaths = tests/python
pythonpath = python
addopts = -v --tb=short
markers =
    e2e: интеграционные E2E-тесты
```

### 15.4 `playwright.config.ts`

```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  retries: 1,
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npx next dev --port 3000',
    port: 3000,
    reuseExistingServer: true,
  },
})
```

---

> **Итого (v3.0):** ~168 тест-кейсов, ~2150 LOC тестового кода, покрытие всех ключевых файлов приложения. По сравнению с v2.0 (234 теста, ~3025 LOC) — сокращение на 28 % при сохранении всех P0-тестов и критических P1-проверок. Все P2-тесты и дублирующие проверки удалены.
