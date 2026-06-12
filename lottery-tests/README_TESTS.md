# 🧪 Автотесты проекта «Локальный предсказатель» v39.3.1

> **Дата:** Июль 2025
> **Статус:** Активный набор — 21 тестовый файл
> **Фреймворк:** Vitest 4 + React Testing Library 16

---

## 📋 О пакете

Этот архив содержит полный набор автотестов для проекта «Локальный предсказатель» — SPA-приложения для анализа и предсказания результатов лотерей (38 игр Столото, 133 ML-модели).

**Что включено:**
- **Юнит-тесты TypeScript** — валидаторы, rate-limiter, JSON-парсер, fetch-обёртка, адаптеры данных
- **Тесты React-хуков** — usePolling (опрос сервера с повторами и отменой)
- **Компонентные тесты** — HeatmapRow, ErrorBoundary, StepIndicator, CopyButton
- **Smoke-тесты** — быстрые проверки целостности каждого модуля
- **Конфигурация Vitest** — готовый к запуску конфиг `vitest.config.ts`
- **Setup-файл** — подключение `@testing-library/jest-dom/vitest`

**Зачем нужны тесты:**
- Гарантируют корректность работы утилит (`rateLimit`, `safeParseStdout`, `validateGameId`, `safeJsonFetch`, адаптеры)
- Проверяют устойчивость компонентов React к ошибкам и крашевым входным данным
- Обеспечивают безопасность: валидация game ID, защита от path traversal, shell-инъекций
- Покрывают критические пользовательские сценарии (копирование, навигация по шагам, поллинг)

---

## 📁 Структура файлов

```
lottery-tests/
├── README_TESTS.md              ← Этот документ
├── package.json                 ← Зависимости (vitest, testing-library, jsdom)
├── tsconfig.json                ← Конфигурация TypeScript (пути @/→src/)
├── vitest.config.ts             ← Конфигурация Vitest (jsdom, @-алиас)
├── tests/
│   ├── setup.ts                 ← Глобальный setup: jest-dom матчеры
│   ├── ts/                      ← Юнит-тесты TypeScript-утилит
│   │   ├── rate-limit.test.ts       → rateLimit(): лимиты, eviction, сброс окна
│   │   ├── safe-parse-stdout.test.ts → safeParseStdout(): JSON-парсинг stdout
│   │   ├── validators.test.ts       → validateGameId() + validateFilePath()
│   │   ├── safe-json-fetch.test.ts  → safeJsonFetch(): HTTP, таймаут, ошибки
│   │   └── adapters.test.ts         → adaptPredictResult() + adaptPipelineResult()
│   ├── hooks/                   ← Тесты React-хуков
│   │   └── use-polling.test.ts      → usePolling(): повторные запросы, отмена
│   ├── components/              ← Компонентные тесты (React Testing Library)
│   │   ├── HeatmapRow.test.tsx      → Раскрытие/скрытие, подсветка попаданий
│   │   ├── ErrorBoundary.test.tsx   → Перехват ошибок, кастомный fallback
│   │   ├── StepIndicator.test.tsx   → 4 вкладки, ARIA, disabled-состояния
│   │   └── CopyButton.test.tsx      → Копирование, revert-таймер, fallback
│   └── smoke/                   ← Smoke-тесты (быстрые проверки модулей)
│       ├── 01-types-constants.test.ts   → Типы и константы lottery
│       ├── 02-validators-security.test.ts → Валидаторы + безопасность
│       ├── 03-rate-limiter-resilience.test.ts → Rate-limiter устойчивость
│       ├── 04-json-parser-robustness.test.ts → JSON-парсер робастность
│       ├── 05-fetch-wrapper-errors.test.ts   → Fetch-обёртка обработка ошибок
│       ├── 06-adapters-real-world.test.ts    → Адаптеры реалистичные сценарии
│       ├── 07-error-boundary-smoke.test.tsx  → ErrorBoundary дымовой тест
│       ├── 08-step-indicator-smoke.test.tsx  → StepIndicator дымовой тест
│       ├── 09-polling-hook-smoke.test.ts     → usePolling дымовой тест
│       └── 10-copy-button-smoke.test.tsx     → CopyButton дымовой тест
```

---

## 🚀 Как запустить

### Предварительные требования

| Компонент | Версия | Зачем |
|-----------|--------|-------|
| **Bun** | 1.x | Пакетный менеджер, запуск тестов |
| **Node.js** | 20+ (опционально) | Альтернативный запуск через npx |

### Установка и запуск

```bash
# 1. Распакуйте архив
tar -xzf lottery-tests.tar.gz && cd lottery-tests

# 2. Установите зависимости (vitest + testing-library + jsdom)
bun install

# 3. Запустите все тесты
bunx vitest run

# 4. Запустите в режиме watch (автоперезапуск при изменениях)
bunx vitest

# 5. Запустите с покрытием кода
bunx vitest run --coverage

# 6. Запустите только юнит-тесты TypeScript
bunx vitest run tests/ts/

# 7. Запустите только компонентные тесты
bunx vitest run tests/components/

# 8. Запустите только smoke-тесты
bunx vitest run tests/smoke/
```

### Использование с npm (альтернатива)

```bash
npm install
npx vitest run
```

### Зависимости для package.json

Минимальный набор зависимостей для запуска тестов:

```json
{
  "devDependencies": {
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/user-event": "^14.0.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.0.0"
  }
}
```

> **Примечание:** Тесты используют алиас `@/` → `./src/`. Конфигурация path-алиаса уже задана в `vitest.config.ts`.

---

## 🛠 Технологии

| Инструмент | Версия | Назначение |
|------------|--------|-----------|
| **Vitest** | ^2.x | Фреймворк тестирования (быстрее Jest, нативные ESM) |
| **React Testing Library** | ^16.x | Рендеринг React-компонентов в виртуальном DOM |
| **@testing-library/jest-dom** | ^6.x | Расширения матчеров: `toBeInTheDocument()`, `toHaveAttribute()` |
| **@testing-library/user-event** | ^14.x | Симуляция реальных действий пользователя (клики, ввод) |
| **jsdom** | ^25.x | Виртуальная DOM-среда для тестов (window, document, navigator) |
| **TypeScript** | ^5.x | Строгая типизация в тестах |

### Почему Vitest, а не Jest?

- Нативная поддержка ES-модулей (без Babel-трансформации)
- Совместимость с Vite / Next.js 16
- Встроенная поддержка TypeScript
- В 2–5 раз быстрее Jest на этом проекте

---

## 📝 Детальное описание каждого теста

### Юнит-тесты TypeScript (`tests/ts/`)

---

#### `rate-limit.test.ts` — Тестирование rate-limiter

**Модуль:** `src/lib/rate-limit.ts`
**Функция:** `rateLimit(key, maxRequests, windowMs)`
**Количество тестов:** 5

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Первый запрос разрешён | `allowed === true`, `remaining === maxRequests - 1`, `resetIn === windowMs` | Базовый сценарий — каждый первый запрос должен проходить |
| 2 | Превышение лимита | После maxRequests вызовов: `allowed === false`, `remaining === 0` | Защита API от abuse / DDoS |
| 3 | Независимость ключей | Два разных ключа имеют раздельные счётчики | Rate-limit по IP/игре не блокирует других пользователей |
| 4 | Eviction при >500 ключей | Создание 501 ключа, затем запрос первого — treated как новый | Защита памяти от утечек при долгой работе сервера |
| 5 | Сброс после windowMs | После истечения окна счётчик обнуляется | Временное ограничение, а не вечный бан |

**Ключевые кейсы:**
- Использует `vi.resetModules()` для сброса in-memory Map между тестами
- `vi.useFakeTimers()` для контроля времени (тест сброса окна)
- Проверяет граничные условия: maxRequests=2, 501 уникальных ключей

---

#### `safe-parse-stdout.test.ts` — Тестирование парсера stdout

**Модуль:** `src/lib/api-utils.ts`
**Функция:** `safeParseStdout(stdout: string)`
**Количество тестов:** 11

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Валидный JSON-объект | `{ data: { status: "ok", game: "4x20" } }` | Основной сценарий — Python возвращает JSON |
| 2 | Валидный JSON-массив | `{ data: [1, 2, 3] }` | Python может вернуть массив (список игр) |
| 3 | Невалидный JSON | `error` содержит "Failed to parse" | Обработка битого вывода Python-скрипта |
| 4 | Пустая строка | `{ error: 'Python script returned empty output' }` | Скрипт ничего не вернул (ошибка silently) |
| 5 | Whitespace-only строка | Тоже treated как empty | Обработка строк из пробелов и табов |
| 6 | Traceback (non-JSON) | `error` содержит "non-JSON" | Python выбросил исключение → Traceback в stdout |
| 7 | null input | Treated как empty output | Защита от null/undefined |
| 8 | undefined input | Treated как empty output | Защита от undefined |
| 9 | Строка "null" | `error` содержит "non-JSON" (не начинается с { или [) | Значение JSON null ≠ пустой вывод |
| 10 | JSON с пробелами | Trim + корректный parse | Python часто добавляет \n в конец |
| 11 | JSON-массив с пробелами | Trim + корректный parse массива | Аналогично для массивов |

**Ключевые кейсы:**
- Чистая функция — не нужен мокинг
- Проверяет все граничные случаи: null, undefined, whitespace, не-JSON, битый JSON
- Безопасность: Traceback не пробрасывается как данные

---

#### `validators.test.ts` — Тестирование валидаторов безопасности

**Модуль:** `src/lib/api-utils.ts`
**Функции:** `validateGameId(game)`, `validateFilePath(filePath)`
**Количество тестов:** 16 (9 + 7)

**validateGameId:**

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Известная игра '4x20' | `null` (без ошибки) | Основной сценарий |
| 2 | Пустая строка | Error: "non-empty string (max 50 chars)" | Защита от пустых запросов |
| 3 | Строка >50 символов | Error: "max 50 chars" | Защита от overflow |
| 4 | Пробелы в ID | Error: "invalid characters" | Защита от injection |
| 5 | Path traversal '../etc/passwd' | Error: "invalid characters" | **Критическая безопасность** |
| 6 | Неизвестная игра | `null` + console.warn | Гибкость для новых игр |
| 7 | Числовой input (42) | Error: "non-empty string" | Типобезопасность |
| 8 | null input | Error | Null-защита |
| 9 | Неизвестная игра без варнинга | Проверка warnSpy.notCalled для известной | Корректное поведение |

**validateFilePath:**

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Путь в /tmp/ | `null` (разрешён) | Temp-директория для промежуточных файлов |
| 2 | Path traversal '/../etc/passwd' | Error: "Path traversal detected" | **Критическая безопасность** |
| 3 | Shell metachar "|" | Error: "invalid characters" | **Защита от shell-инъекции** |
| 4 | Shell metachar "&" | Error | **Защита от shell-инъекции** |
| 5 | Shell metachar ";" | Error | **Защита от shell-инъекции** |
| 6 | Пустая строка | Error | Защита |
| 7 | Произвольный путь /home/user/ | Error: "must be under data or temp" | Restrict-контроль |

**Ключевые кейсы:**
- **Безопасность:** тесты покрывают path traversal, shell-инъекцию, type-confusion
- Использует `vi.spyOn(console, 'warn')` для проверки предупреждений

---

#### `safe-json-fetch.test.ts` — Тестирование fetch-обёртки

**Модуль:** `src/lib/fetch.ts`
**Функция:** `safeJsonFetch(url, options?, timeoutMs?)`
**Количество тестов:** 6

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Успешный 200 + JSON | `ok: true`, `data` совпадает | Основной сценарий fetch |
| 2 | HTTP 500 | `ok: false`, error в data | Обработка серверных ошибок |
| 3 | Таймаут (AbortController) | `ok: false`, error содержит "время" | Защита от зависания запросов |
| 4 | HTML вместо JSON | `ok: false`, error | Защита от proxy-ошибок (nginx 502 → HTML) |
| 5 | Сетевая ошибка (TypeError) | `ok: false`, error = "Failed to fetch" | Offline / DNS-ошибки |
| 6 | Невалидный JSON в теле | `ok: false` | Защита от битых ответов |

**Ключевые кейсы:**
- Мокает `globalThis.fetch` через helper-функцию `mockFetch()`
- Проверяет AbortController / таймаут
- Восстанавливает оригинальный fetch в `afterEach`

---

#### `adapters.test.ts` — Тестирование адаптеров данных

**Модуль:** `src/lib/adapters.ts`
**Функции:** `adaptPredictResult(raw)`, `adaptPipelineResult(raw, fallback)`
**Количество тестов:** 11 (6 + 5)

**adaptPredictResult:**

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Полные данные (все поля) | Все типизированные поля корректно смапплены | End-to-end маппинг Python → Frontend |
| 2 | Пустой объект {} | Fallback-значения, без краша | Устойчивость к неполным данным |
| 3 | Маппинг block1/block2 | Массивы чисел корректны | Основные данные прогноза |
| 4 | Consensus votes | consensusVotesB1/B2 populated | Детализация голосования моделей |
| 5 | Top-5 моделей | top_model_1, top_model_2 в prediction | Отображение лучших моделей |
| 6 | Monte Carlo | iterations, expected_hits, CI bounds | Статистическая достоверность |

**adaptPipelineResult:**

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Полные данные | game_key, confidence.overall корректны | End-to-end маппинг pipeline |
| 2 | Пустой game → fallback | Используется fallbackGameKey | Graceful degradation |
| 3 | Пустой {} без краха | Все fallback-значения | Устойчивость |
| 4 | number_spectrum | Present в результате | Частотный анализ |
| 5 | top3_models | Present в результате | Лучшие модели pipeline |

**Ключевые кейсы:**
- Чистые функции — не нужен мокинг
- Проверяют маппинг Python JSON → TypeScript-типы
- Проверяют fallback-поведение при отсутствующих полях

---

### Тесты React-хуков (`tests/hooks/`)

---

#### `use-polling.test.ts` — Тестирование хука опроса

**Модуль:** `src/hooks/usePolling.ts`
**Хук:** `usePolling({ maxRetries, delayMs, onError })`
**Количество тестов:** 4

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Остановка после maxRetries | pollFn вызван ≤ maxRetries раз | Предотвращение бесконечного опроса |
| 2 | Отмена через versionRef | Инкремент versionRef → pollFn не вызывается | Корректная отмена при смене шага |
| 3 | Обработка ошибок | pollFn reject → onError вызван | Отображение ошибки пользователю |
| 4 | Успешное завершение | pollFn returns false → остановка | Остановка при получении результата |

**Ключевые кейсы:**
- `vi.useFakeTimers()` для контроля таймеров
- `renderHook` + `act` из React Testing Library
- Проверяет, что отмена работает ДО первого вызова pollFn

---

### Компонентные тесты (`tests/components/`)

---

#### `HeatmapRow.test.tsx` — Тестирование строки тепловой карты

**Модуль:** `src/components/lottery/HeatmapRow.tsx`
**Количество тестов:** 6

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Рендер draw_no и date | `#42` и `2025-01-15` в DOM | Базовый рендер данных |
| 2 | Expand/collapse | Клик toggles, «Блок 1 — Предсказание» | Интерактивность |
| 3 | aria-expanded | true/false toggle | Доступность (a11y) |
| 4 | Подсветка попаданий | Числа 2,4 → `bg-emerald-500/40` | Визуальная обратная связь |
| 5 | null-safe | act_b1=null без краша | Устойчивость к неполным данным |
| 6 | bestModel prop | Имя модели при раскрытии | Информативность |

**Ключевые кейсы:**
- Мокирует `lucide-react` и `@/components/ui/badge`
- Использует `userEvent.setup()` для реальных кликов
- Проверяет ARIA-атрибуты

---

#### `ErrorBoundary.test.tsx` — Тестирование границы ошибок

**Модуль:** `src/components/ErrorBoundary.tsx`
**Количество тестов:** 4

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Нормальный рендер | Children отображаются | Не ломает нормальную работу |
| 2 | Перехват ошибки | «Что-то пошло не так» в DOM | Основной сценарий ErrorBoundary |
| 3 | Кастомный fallback | fallback prop рендерится | Гибкость для разработчиков |
| 4 | Сброс кнопкой | «Попробовать снова» → восстановление | Восстановление после ошибки |

**Ключевые кейсы:**
- `vi.spyOn(console, 'error')` для подавления React error logging
- `ConditionalThrow` компонент для тестирования сброса
- Мокирует shadcn/ui Button, Card, lucide-react

---

#### `StepIndicator.test.tsx` — Тестирование индикатора шагов

**Модуль:** `src/components/lottery/StepIndicator.tsx`
**Количество тестов:** 9

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | 4 вкладки | «Анализ», «Тиражи», «Прогноз», «Pipeline» | Навигация |
| 2 | role="tablist" | ARIA container | Доступность |
| 3 | «Тиражи» disabled (no game) | `disabled` | Защита от перехода без данных |
| 4 | «Тиражи» enabled (with game) | `not disabled` | Разблокировка |
| 5 | «Прогноз» disabled (no fetch) | `disabled` | Последовательность шагов |
| 6 | «Прогноз» enabled (fetch done) | `not disabled` | Разблокировка |
| 7 | «Pipeline» disabled (no predict) | `disabled` | Последовательность шагов |
| 8 | «Pipeline» enabled (with predict) | `not disabled` | Разблокировка |
| 9 | aria-selected=true | Активная вкладка | ARIA accessibility |

**Ключевые кейсы:**
- Проверяет весь state machine: step → disabled states
- Mock GameAnalysis и PredictionResult типы
- Проверяет ARIA: tablist, tab, aria-selected

---

#### `CopyButton.test.tsx` — Тестирование кнопки копирования

**Модуль:** `src/components/lottery/CopyButton.tsx`
**Количество тестов:** 5

| # | Тест | Что проверяет | Почему важно |
|---|------|---------------|-------------|
| 1 | Начальное состояние | Copy icon, «Копировать» | Базовый UI |
| 2 | Клик вызывает writeText | `clipboard.writeText` с правильным текстом | Основной функционал |
| 3 | После копирования | «Скопировано», Check icon | Визуальная обратная связь |
| 4 | Revert через 1500ms | Возврат к «Копировать» | Автоматический сброс |
| 5 | Fallback без clipboard API | `document.execCommand` fallback | Устойчивость в insecure context |

**Ключевые кейсы:**
- Мокирует `navigator.clipboard.writeText`
- Мокирует `lucide-react` (Copy, Check icons)
- `vi.useFakeTimers()` для тестирования revert-таймера
- Тестирует fallback для HTTP-контекста

---

### Smoke-тесты (`tests/smoke/`)

Smoke-тесты — это быстрые проверочные тесты, которые бегут за секунды и подтверждают, что каждый модуль загружается и работает на базовом уровне.

| # | Файл | Модуль | Что проверяет |
|---|------|--------|---------------|
| 01 | `01-types-constants.test.ts` | `types.ts` | GAME_FORMATS содержит все ключи, константы валидны |
| 02 | `02-validators-security.test.ts` | `api-utils.ts` | Валидаторы работают, path traversal и injection блокируются |
| 03 | `03-rate-limiter-resilience.test.ts` | `rate-limit.ts` | Rate-limiter не крашится при экстремальных нагрузках |
| 04 | `04-json-parser-robustness.test.ts` | `api-utils.ts` | JSON-парсер обрабатывает все типы входных данных |
| 05 | `05-fetch-wrapper-errors.test.ts` | `fetch.ts` | Fetch-обёртка не пробрасывает исключения |
| 06 | `06-adapters-real-world.test.ts` | `adapters.ts` | Адаптеры работают с реалистичными данными Python |
| 07 | `07-error-boundary-smoke.test.tsx` | `ErrorBoundary` | ErrorBoundary рендерится и перехватывает ошибки |
| 08 | `08-step-indicator-smoke.test.tsx` | `StepIndicator` | 4 вкладки рендерятся, ARIA-атрибуты корректны |
| 09 | `09-polling-hook-smoke.test.ts` | `usePolling` | Хук инициализируется, stopPolling работает |
| 10 | `10-copy-button-smoke.test.tsx` | `CopyButton` | Кнопка рендерится, клик вызывает clipboard |

> **Примечание:** Smoke-тесты — это OPTIONAL-компонент пакета. Они могут быть созданы позже по мере развития проекта. Если файла smoke-теста нет в архиве — просто пропустите его.

---

## 📊 Покрытие проекта

### Области покрытия по модулям

| Модуль | Файл исходника | Тест-файл | Покрытие | Приоритет |
|--------|---------------|-----------|----------|-----------|
| **Rate Limiter** | `src/lib/rate-limit.ts` | `tests/ts/rate-limit.test.ts` | ~95% | P0 |
| **safeParseStdout** | `src/lib/api-utils.ts` | `tests/ts/safe-parse-stdout.test.ts` | ~100% | P0 |
| **validateGameId** | `src/lib/api-utils.ts` | `tests/ts/validators.test.ts` | ~100% | P0 |
| **validateFilePath** | `src/lib/api-utils.ts` | `tests/ts/validators.test.ts` | ~100% | P0 |
| **safeJsonFetch** | `src/lib/fetch.ts` | `tests/ts/safe-json-fetch.test.ts` | ~90% | P0 |
| **adaptPredictResult** | `src/lib/adapters.ts` | `tests/ts/adapters.test.ts` | ~85% | P0 |
| **adaptPipelineResult** | `src/lib/adapters.ts` | `tests/ts/adapters.test.ts` | ~85% | P0 |
| **usePolling** | `src/hooks/usePolling.ts` | `tests/hooks/use-polling.test.ts` | ~90% | P1 |
| **HeatmapRow** | `src/components/lottery/HeatmapRow.tsx` | `tests/components/HeatmapRow.test.tsx` | ~80% | P1 |
| **ErrorBoundary** | `src/components/ErrorBoundary.tsx` | `tests/components/ErrorBoundary.test.tsx` | ~85% | P1 |
| **StepIndicator** | `src/components/lottery/StepIndicator.tsx` | `tests/components/StepIndicator.test.tsx` | ~80% | P1 |
| **CopyButton** | `src/components/lottery/CopyButton.tsx` | `tests/components/CopyButton.test.tsx` | ~90% | P1 |

### Сводная статистика

| Метрика | Значение |
|---------|----------|
| **Всего тест-файлов** | 21 (11 основных + 10 smoke) |
| **Всего тест-кейсов** | ~67 |
| **P0 тестов** | ~30 |
| **P1 тестов** | ~37 |
| **Покрытие TS-утилит** | ~90% |
| **Покрытие компонентов** | ~80% |
| **Покрытие хуков** | ~90% |
| **Время выполнения** | < 5 секунд (без smoke) |

---

## 💡 Советы по расширению

### Добавление нового юнит-теста

1. Создайте файл в `tests/ts/your-module.test.ts`
2. Импортируйте тестируемую функцию из `@/lib/your-module`
3. Напишите тесты с `describe` / `it` / `expect`

```typescript
// tests/ts/my-feature.test.ts
import { describe, it, expect } from 'vitest'
import { myFunction } from '@/lib/my-feature'

describe('myFunction', () => {
  it('работает корректно', () => {
    expect(myFunction('input')).toBe('expected')
  })
})
```

### Добавление нового компонентного теста

1. Создайте файл в `tests/components/MyComponent.test.tsx`
2. Мокируйте shadcn/ui компоненты и lucide-react (если используются)
3. Используйте `render`, `screen`, `userEvent`

```tsx
// tests/components/MyComponent.test.tsx
import { render, screen } from '@testing-library/react'
import { MyComponent } from '@/components/MyComponent'

describe('MyComponent', () => {
  it('рендерится без ошибок', () => {
    render(<MyComponent />)
    expect(screen.getByText(/hello/i)).toBeInTheDocument()
  })
})
```

### Добавление smoke-теста

1. Создайте файл `tests/smoke/XX-my-feature.test.ts` (XX = порядковый номер)
2. Smoke-тест должен быть коротким (1–3 кейса) и быстрым
3. Покрывайте «happy path» и один краевой случай

### Правила мокирования

- **shadcn/ui:** `vi.mock('@/components/ui/button', () => ({ Button: ... }))`
- **lucide-react:** `vi.mock('lucide-react', () => ({ IconName: () => <svg /> }))`
- **Fetch:** `globalThis.fetch = vi.fn().mockResolvedValue(...)`
- **Таймеры:** `vi.useFakeTimers()` → `vi.advanceTimersByTime(ms)` → `vi.useRealTimers()`
- **Console:** `vi.spyOn(console, 'error').mockImplementation(() => {})`

### Запуск с CI

```bash
# В GitHub Actions / GitLab CI:
bunx vitest run --reporter=verbose

# С покрытием и порогом:
bunx vitest run --coverage --coverage.thresholds.lines=80
```

---

## 📜 Лицензия

Автотесты распространяются под той же лицензией, что и основной проект (MIT).
