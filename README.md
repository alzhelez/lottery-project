# 🎰 Локальный предсказатель — Лотерейный анализатор
**Версия 39.5.1** | Next.js 16 + Bun + Python 3 | 38 игр Столото | 133 ML-модели

---

## 📋 Системные требования

| Компонент | Минимальная версия | Рекомендуемая | Где скачать |
|-----------|-------------------|---------------|-------------|
| **Bun** | 1.x | 1.1+ | https://bun.sh |
| **Python** | 3.10 | 3.11+ | https://python.org |
| **Node.js** | 20+ (опционально) | 22+ | https://nodejs.org |
| **ОЗУ** | 2 ГБ | 4 ГБ+ | — |
| **Место на диске** | 500 МБ | 1 ГБ+ | — |
| **ОС** | Windows 10, macOS 12, Ubuntu 20.04+ | — | — |

> **Примечание:** Bun — основной пакетный менеджер. Node.js нужен только если вы предпочитаете `npm` вместо `bun`.

---

## 🚀 Быстрый старт (5 минут)

Если вы знакомы с терминалом — вот минимальные 4 шага:

```bash
# 1. Распакуйте архив
tar -xzf lottery-project.tar.gz && cd lottery-project

# 2. Установите все зависимости (Node.js + Python)
bun install
pip install requests numpy scipy pandas plotly

# 3. Инициализируйте базу данных
bunx prisma db push

# 4. Запустите! → http://localhost:3000
bun run dev
```

Откройте **http://localhost:3000** в браузере. При первом запуске данные загрузятся автоматически.

---

## 📖 Подробная установка — Windows

### Предварительные требования

1. **Bun** — откройте PowerShell и выполните:
   ```powershell
   powershell -c "irm bun.sh/install.ps1 | iex"
   ```
   Перезапустите PowerShell после установки.

2. **Python 3.10+** — скачайте с https://python.org, запустите установщик.
   > ⚠️ **Обязательно** поставьте галочку **"Add Python to PATH"** внизу установщика!

3. **Git for Windows** (опционально) — https://git-scm.com — нужен только если планируете version control.

### Шаг 1. Распаковка архива

```powershell
# Если используете PowerShell:
Expand-Archive -Path lottery-project.tar.gz -DestinationPath .

# Или через командную строку (если установлен tar):
tar -xzf lottery-project.tar.gz

# Или распакуйте вручную через WinRAR / 7-Zip
cd lottery-project
```

### Шаг 2. Установка Node.js-зависимостей

```powershell
bun install
```

Если возникает ошибка — попробуйте:
```powershell
bun install --legacy-peer-deps
```

### Шаг 3. Установка Python-зависимостей

```powershell
# Проверьте, что Python установлен и доступен:
python --version
# Должно вывести: Python 3.10.x (или выше)

# Установите необходимые пакеты:
pip install requests numpy scipy pandas plotly
```

Если `python` не найден — попробуйте `python3` или `py`.

### Шаг 4. Настройка базы данных (Prisma)

Файл `.env` уже создан в архиве и содержит:
```
DATABASE_URL="file:./custom.db"
```

Выполните:
```powershell
bunx prisma generate
bunx prisma db push
```

Это создаст файл SQLite `custom.db` в корне проекта.

### Шаг 5. Первый запуск

```powershell
bun run dev
```

Откройте браузер по адресу **http://localhost:3000**. При первом запуске страница может загружаться до 30 секунд — это нормальное поведение (сборка Next.js).

---

## 📖 Подробная установка — macOS

### Предварительные требования

```bash
# Установите Homebrew (если ещё нет):
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установите Bun:
brew install bun

# Python обычно уже установлен, но для обновления:
brew install python@3.11
```

### Шаг 1. Распаковка

```bash
tar -xzf lottery-project.tar.gz
cd lottery-project
```

### Шаг 2. Зависимости

```bash
# Node.js-зависимости:
bun install

# Python-зависимости (используйте pip3 на macOS):
pip3 install requests numpy scipy pandas plotly
```

Если `pip3` не найден — установите через:`curl https://bootstrap.pypa.io/get-pip.py | python3`

### Шаг 3. База данных

```bash
bunx prisma generate
bunx prisma db push
```

### Шаг 4. Запуск

```bash
bun run dev
```

Перейдите на **http://localhost:3000**.

---

## 📖 Подробная установка — Linux (Ubuntu/Debian)

### Предварительные требования

```bash
# Обновите систему:
sudo apt update && sudo apt upgrade -y

# Установите Python и pip:
sudo apt install -y python3 python3-pip python3-venv

# Установите Bun:
curl -fsSL https://bun.sh/install | bash
# Перезапустите терминал или:
source ~/.bashrc
```

### Шаг 1. Распаковка

```bash
tar -xzf lottery-project.tar.gz
cd lottery-project
```

### Шаг 2. Зависимости

```bash
# Node.js-зависимости:
bun install

# Python-зависимости:
pip3 install --user requests numpy scipy pandas plotly

# Если нужны права root:
sudo pip3 install requests numpy scipy pandas plotly
```

### Шаг 3. База данных

```bash
bunx prisma generate
bunx prisma db push
```

### Шаг 4. Запуск

```bash
bun run dev
```

Перейдите на **http://localhost:3000**.

> **Совет:** Если используете удалённый сервер — пробросьте порт через SSH:`ssh -L 3000:localhost:3000 user@server`

---

## 📁 Структура проекта

```
lottery-project/
├── src/                        # Исходный код Next.js приложения
│   ├── app/                    # Страницы, layout и API-маршруты
│   │   ├── page.tsx             # Главная страница (многошаговый визард)
│   │   ├── layout.tsx           # Корневой layout с ThemeProvider
│   │   ├── globals.css          # Глобальные стили (Tailwind)
│   │   └── api/                 # Server API endpoints
│   │       ├── download-project/  # Скачивание проекта как архив
│   │       └── ...               # Другие API маршруты
│   ├── components/             # React UI компоненты (shadcn/ui)
│   │   ├── ui/                  # Базовые компоненты (Button, Card, Tabs...)
│   │   └── ...                  # Специфичные компоненты приложения
│   ├── hooks/                  # React хуки (custom hooks)
│   └── lib/                    # Утилиты и вспомогательный код
│       ├── python-runner.ts     # Запуск Python-скриптов из Node.js
│       ├── db.ts                # Работа с Prisma/SQLite
│       └── utils.ts             # Общие утилиты (cn, formatters)
├── python/                     # Python анализаторы и ML-модели
│   ├── analyze.py              # Основной анализ — 38 игр Столото
│   ├── predict.py              # Генерация прогнозов (133 ML-модели)
│   ├── fetch.py                # Обёртка для загрузки тиражей
│   ├── fetch_draws.py          # HTTP-клиент для API Столото
│   ├── stoloto_analyzer_v3.py  # Статистический анализатор (API)
│   ├── pipeline.py             # Pipeline-анализ прогнозов
│   ├── lottery_pipeline.py     # Анализатор HTML/CSV отчётов
│   ├── lp_v130_app.py          # Приложение-анализатор v130
│   └── api_wrapper.py          # Обёртка для API запросов
├── docs/                       # Документация проекта
│   ├── ARCHITECTURE.md         # Подробная архитектура системы
│   └── TEST_PLAN.md            # План тестирования
├── data/                       # Файлы тиражей (создаётся при загрузке)
├── prisma/                     # Схема и миграции базы данных
│   └── schema.prisma           # Prisma-схема (SQLite)
├── public/                     # Статические файлы (иконки, manifest)
├── .env                        # DATABASE_URL (создаётся автоматически)
├── .gitignore                  # Список игнорируемых файлов
├── package.json                # Зависимости и скрипты Node.js
├── next.config.ts              # Конфигурация Next.js 16
├── tailwind.config.ts          # Конфигурация Tailwind CSS
├── tsconfig.json               # Конфигурация TypeScript
├── eslint.config.mjs           # Конфигурация ESLint
├── postcss.config.mjs          # Конфигурация PostCSS
└── components.json             # Конфигурация shadcn/ui
```

---

## 🎯 Как пользоваться

Приложение представляет собой **4-шаговый визард**:

### Шаг 1 — Загрузка данных
- Выберите игры для анализа (или все 38 сразу)
- Нажмите **«Загрузить тиражи»**
- Система скачает последние 100–500 тиражей для каждой игры с сервера Столото
- Данные сохраняются локально в папку `data/`

### Шаг 2 — Анализ
- Нажмите **«Запустить анализ»**
- Python-скрипт обработает все загруженные тиражи
- Расчёт статистики, частот, разрывов, корреляций
- ⏱ Первый анализ может занять 2–5 минут (зависит от количества игр)

### Шаг 3 — Прогнозы
- Нажмите **«Сгенерировать прогнозы»**
- 133 ML-модели создадут прогнозы для каждой игры
- Результаты отображаются в таблице с фильтрами

### Шаг 4 — Результаты
- Просмотр прогнозов в виде таблицы
- Сортировка по играм, confidence score
- Экспорт данных

---

## 📊 Документация

В архив включена подробная документация:

| Файл | Содержание |
|------|-----------|
| `docs/ARCHITECTURE.md` | Полное описание архитектуры: компоненты, API, Python-модули, схема БД, flow данных |
| `docs/TEST_PLAN.md` | План тестирования: юнит-тесты, интеграционные тесты, e2e сценарии |

---

## ⚠️ Решение проблем (FAQ)

### ❌ Python не найден (Windows)

**Симптом:** Ошибка `python: command not found` или `spawn python ENOENT`

**Решение:**
1. Убедитесь, что при установке Python была поставлена галочка **"Add Python to PATH"**
2. Переустановите Python с этой галочкой
3. Проверьте: `python --version` и `pip --version`
4. Если установлен Python 3.x но команда `python` не работает — используйте `py` или `python3`
5. Проверьте переменные окружения: System Properties → Environment Variables → Path — должен содержать путь к Python

### ❌ `bun install` не удаётся

**Симптом:** Ошибки peer dependencies или сетевые ошибки.

**Решение:**
```bash
# Попробуйте с флагом:
bun install --legacy-peer-deps

# Если не помогает — очистите кеш:
bun install --force

# Альтернативно — используйте npm:
npm install --legacy-peer-deps
```

### ❌ Ошибки Prisma (не создаётся база данных)

**Симптом:** `Error: P1001` или `prisma db push failed`

**Решение:**
```bash
# 1. Убедитесь, что .env файл существует:
cat .env
# Должно содержать: DATABASE_URL="file:./custom.db"

# 2. Перегенерируйте клиент Prisma:
bunx prisma generate

# 3. Создайте базу данных:
bunx prisma db push

# 4. Если всё ещё не работает — удалите старую БД и повторите:
rm -f custom.db
bunx prisma db push
```

### ❌ Порт 3000 занят

**Симптом:** `Error: Port 3000 is already in use`

**Решение:**
```bash
# Запустите на другом порту:
bun run dev -- -p 3001

# Или убейте процесс, занимающий порт 3000:
# Linux/macOS:
lsof -ti:3000 | xargs kill -9

# Windows (PowerShell):
Stop-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess -Force
```

### ❌ Белая страница при первом запуске

**Симптом:** Страница загружается, но отображается пустой экран.

**Причина:** Next.js компилирует страницы при первом запросе («lazy compilation»). Это занимает 10–30 секунд.

**Решение:** Подождите 30 секунд и обновите страницу (F5). Откройте DevTools (F12) → Console, чтобы проверить наличие ошибок.

### ❌ Анализ занимает слишком много времени

**Симптом:** Шаг анализа работает дольше 10 минут.

**Причина:** При первом запуске Python загружает ML-модели и кеширует данные.

**Решение:** Первый анализ всегда самый долгий. Последующие запуски используют кешированные данные и работают значительно быстрее (30–60 секунд).

Если проблема сохраняется:
- Проверьте, что в `data/` есть файлы тиражей (не пустые)
- Уменьшите количество игр для анализа
- Проверьте логи в терминале где запущен dev-сервер

### ❌ Таймаут прогноза

**Симптом:** Прогноз прерывается через некоторое время.

**Решение:** Уменьшите количество одновременно анализируемых игр. Запускайте прогноз по 5–10 игр за раз вместо всех 38.

### ❌ Хочу использовать npm вместо bun

```bash
# Замените все команды bun на npm:
npm install
npx prisma db push
npx prisma generate
npx next dev
```

> Bun работает значительно быстрее npm, но npm тоже поддерживается.

### ❌ Ошибка прав доступа (Linux)

**Симптом:** `EACCES: permission denied`

**Решение:**
```bash
# Не используйте sudo с bun/npm! Вместо этого:
# 1. Исправьте права доступа к проекту:
sudo chown -R $(whoami) ~/lottery-project

# 2. Или дайте права на выполнение:
chmod +x node_modules/.bin/*

# 3. Убедитесь, что bun установлен для пользователя, не root:
curl -fsSL https://bun.sh/install | bash
```

### ❌ SQLite: «database is locked»

**Симптом:** `Error: SQLITE_BUSY: database is locked`

**Решение:**
```bash
# 1. Остановите dev-сервер (Ctrl+C)

# 2. Удалите файл БД:
rm -f custom.db

# 3. Пересоздайте базу:
bunx prisma db push

# 4. Запустите снова:
bun run dev
```

---

## 🐍 Python-окружение

### Как Python находится

Проект автоматически ищет интерпретатор Python в следующем порядке:

1. **Виртуальное окружение** (если существует):
   - Windows: `%USERPROFILE%\.venv\Scripts\python.exe`
   - macOS/Linux: `~/.venv/bin/python3`
2. **Системный PATH** — стандартные расположения:
   - Windows: `C:\Python311\python.exe`, `C:\Users\<user>\AppData\Local\Programs\Python\python.exe`
   - macOS: `/usr/bin/python3`, `/usr/local/bin/python3`
   - Linux: `/usr/bin/python3`, `/usr/local/bin/python3`

### Создание виртуального окружения (рекомендуется)

```bash
# Создайте venv в корне проекта:
python -m venv .venv

# Активируйте:
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Установите зависимости:
pip install requests numpy scipy pandas plotly
```

### Необходимые Python-пакеты

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| `requests` | 2.x | HTTP-запросы к API Столото |
| `numpy` | 1.24+ | Математические вычисления |
| `scipy` | 1.10+ | Статистические функции |
| `pandas` | 2.x | Обработка табличных данных |
| `plotly` | 5.x | Визуализация графиков |

### Добавление новых пакетов

```bash
# Установите пакет:
pip install <название_пакета>

# Если используете venv — пакет установится автоматически в правильное место
```

---

## 🔧 Команды и скрипты

| Команда | Описание |
|---------|----------|
| `bun run dev` | Запуск сервера разработки (http://localhost:3000) |
| `bun run build` | Сборка production-версии |
| `bun run start` | Запуск production-сервера |
| `bun run lint` | Проверка кода ESLint |
| `bun run db:push` | Синхронизация схемы БД (Prisma) |
| `bun run db:generate` | Генерация Prisma-клиента |
| `bunx prisma studio` | Открытие Prisma Studio (GUI для БД) |
| `bun install` | Установка Node.js-зависимостей |

---

## 🏛️ Архитектура

Проект построен на архитектуре **Next.js App Router** с гибридным подходом: React-фронтенд + Python-бэкенд для аналитики.

- **Фронтенд** — Next.js 16, React, Tailwind CSS 4, shadcn/ui. Многошаговый визард (4 шага) для загрузки данных, анализа, прогнозирования и просмотра результатов.
- **Бэкенд** — API Routes Next.js обрабатывают HTTP-запросы и вызывают Python-скрипты через `child_process`. Python выполняет статистический анализ и генерацию прогнозов.
- **База данных** — SQLite через Prisma ORM. Хранит историю прогнозов и результаты анализов.
- **Python-модули** — 133 ML-модели для прогнозирования, статистические анализаторы, HTTP-клиенты для API Столото.

Подробное описание архитектуры см. в `docs/ARCHITECTURE.md`.

---

## 🧪 Тестирование

План тестирования включает:
- Юнит-тесты для Python-анализаторов
- Интеграционные тесты для API-маршрутов
- E2E-тесты для пользовательского интерфейса

Подробный план тестирования см. в `docs/TEST_PLAN.md`.

---

## 📜 Лицензия

Проект распространяется под лицензией **MIT**. Вы можете свободно использовать, модифицировать и распространять данный код.
