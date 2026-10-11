import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test, type APIRequestContext } from '@playwright/test'
import * as allure from 'allure-js-commons'

test.describe.configure({ mode: 'serial' })

test.beforeEach(async () => {
  await allure.epic('Интерфейс (сквозные тесты)')
  await allure.feature('Путь пользователя на моке API Столото')
})

const MOCK = 'http://127.0.0.1:3199'

async function runJob(request: APIRequestContext, data: Record<string, unknown>) {
  const { job } = await (await request.post('/api/jobs', { data })).json()
  for (let i = 0; i < 300; i++) {
    const { job: j } = await (await request.get(`/api/jobs/${job.id}`)).json()
    if (j.status !== 'running') return j
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error('задача не завершилась')
}

test('загрузка всех игр через модальное окно и проверка на случайность', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('dialog')).toBeVisible()                 // данных нет — окно открывается само
  await page.getByTestId('start-fetch').click()
  await expect(page.getByTestId('fetch-4x20')).toContainText('Готово', { timeout: 180_000 })
  for (const slug of ['6x45plus', 'top-3', 'ruslotto', 'bingo75', 'duel']) {
    await expect(page.getByTestId(`fetch-${slug}`)).toContainText('Готово')
  }
  await expect(page.getByTestId('fetch-5x36')).toContainText('Нет архива')
  await expect(page.getByTestId('fetch-4x20')).toContainText('1 499')
  await expect(page.getByTestId('scan-status')).toContainText('завершена', { timeout: 120_000 })
  await page.getByRole('button', { name: 'Закрыть окно' }).click()

  const table = page.getByTestId('games-table')
  await expect(table.getByTestId('row-4x20')).toContainText('1 499')
  await expect(table.getByTestId('row-4x20')).toContainText('№13896')
  for (const slug of ['4x20', '6x45plus', 'top-3', 'ruslotto', 'bingo75']) {
    await expect(table.getByTestId(`row-${slug}`)).not.toContainText('не проверялась')
  }
  await expect(table.getByTestId('row-duel')).toHaveCount(0)            // давно нет тиражей — не в основном списке
})

test('устаревшие игры вынесены в отдельный список', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('toggle-obsolete')).toContainText('Устаревшие игры (1)')
  await page.getByTestId('toggle-obsolete').click()
  await expect(page.getByTestId('obsolete-table').getByTestId('row-duel')).toContainText('дн')
  await page.getByRole('link', { name: 'Дуэль' }).click()
  await expect(page.getByTestId('inactive-banner')).toBeVisible()
  await expect(page.getByTestId('next-draw')).toContainText('Игра не проводится')
})

test('страница игры: ссылка, количество тиражей, период, следующий тираж', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: '4 из 20' }).click()
  await expect(page).toHaveURL(/\/games\/4x20$/)
  await expect(page.getByTestId('game-title')).toHaveText('4 из 20')
  await expect(page.getByTestId('stoloto-link')).toHaveAttribute('href', 'https://www.stoloto.ru/4x20/game/')
  await expect(page.getByTestId('draw-count')).toHaveText('1 499')
  await expect(page.getByTestId('period')).toHaveText(/\d{2}\.\d{2}\.\d{4} — \d{2}\.\d{2}\.\d{4}/)
  await expect(page.getByTestId('next-draw')).toContainText('№13896')
  await expect(page.getByTestId('inactive-banner')).toHaveCount(0)
})

test('анализ: тесты случайности и сравнение методов', async ({ page }) => {
  await page.goto('/games/4x20')
  await page.getByTestId('run-analysis').click()
  await expect(page.getByTestId('overview')).toBeVisible({ timeout: 120_000 })
  await expect(page.getByTestId('overview')).toContainText('Равномерность частот')
  await page.getByTestId('tab-methods').click()
  await expect(page.getByTestId('methods-prediction')).toContainText('Прогноз на тираж №13896')
  await expect(page.getByTestId('models-table')).toContainText('Случайный выбор (контроль)')
})

test('режим Бога: запуск, промежуточный и итоговый результат', async ({ page }) => {
  await page.goto('/games/4x20')
  await page.getByTestId('tab-god').click()
  await page.getByTestId('budget').fill('1')
  await page.getByTestId('run-god').click()
  await expect(page.getByTestId('god-progress')).toBeVisible()
  await expect(page.getByTestId('run-god')).toBeVisible({ timeout: 240_000 })
  const result = page.getByTestId('god-result')
  await expect(result).toContainText('Завершено')
  await expect(result).toContainText('Прогноз на тираж №13896')
  await expect(page.getByTestId('timeline').locator('tbody tr')).toHaveCount(30)
})

test('журнал прогнозов: запись до тиража и сверка после загрузки', async ({ page, request }) => {
  await page.goto('/games/4x20')
  await page.getByTestId('tab-journal').click()
  const entries = page.getByTestId('journal-entries')
  await expect(entries.locator('tbody tr')).toHaveCount(3)
  await expect(entries).toContainText('ждёт тиража')
  await expect(entries).toContainText('№13896')

  // тираж №13896 «состоялся» — загружаем его
  expect((await (await request.get(`${MOCK}/__release`)).json()).released).toEqual([13896])
  const job = await runJob(request, { kind: 'fetch', game: '4x20' })
  expect(job.status).toBe('done')
  expect(job.games['4x20'].journal_checked).toBe(3)

  await page.reload()
  await page.getByTestId('tab-journal').click()
  await expect(entries).toContainText('сверен')
  await expect(entries).not.toContainText('ждёт тиража')
  const summary = page.getByTestId('journal-summary')
  for (const title of ['Лучший метод анализа', 'Консенсус методов', 'Режим Бога']) {
    await expect(summary.locator('tr', { hasText: title }).locator('td').nth(1)).toHaveText('1')
  }
  await page.screenshot({ path: 'tests/e2e/.data/journal.png', fullPage: true })
})

test('шансы: точные вероятности и возврат по введённым призам', async ({ page }) => {
  await page.goto('/games/4x20')
  await page.getByTestId('tab-odds').click()
  await expect(page.getByTestId('jackpot-odds')).toHaveText('1 из 23 474 025')
  await page.getByTestId('ticket-price').fill('150')
  await page.getByTestId('prize-4+4').fill('10000000')
  await page.getByTestId('prize-2+2').fill('300')
  await expect(page.getByTestId('ev-summary')).toContainText('Ожидаемый выигрыш')
  await expect(page.getByTestId('return')).not.toHaveText('—')
  await page.getByTestId('save-prizes').click()
  await page.reload()
  await page.getByTestId('tab-odds').click()
  await expect(page.getByTestId('prize-4+4')).toHaveValue('10000000')

  await page.goto('/odds')
  await expect(page.getByTestId('odds-compare')).toContainText('4 из 20')
  await expect(page.getByTestId('odds-compare').locator('tr', { hasText: '4 из 20' })).toContainText('150')
})

test('билеты: непопулярные комбинации и проверка своей', async ({ page }) => {
  await page.goto('/games/6x45plus')
  await page.getByTestId('tab-tickets').click()
  await page.getByTestId('ticket-count').fill('3')
  await page.getByTestId('generate').click()
  await expect(page.getByTestId('ticket-list').locator('li')).toHaveCount(3)
  await page.getByTestId('check-input').fill('1, 2, 3, 10, 11, 12 | 2')
  await page.getByTestId('check').click()
  await expect(page.getByTestId('check-result')).toContainText('похожа на популярный выбор')
  await page.goto('/games/ruslotto')
  await page.getByTestId('tab-tickets').click()
  await page.getByTestId('generate').click()
  await expect(page.getByTestId('tickets')).toContainText('напечатаны заранее')
})

test('экспорт в Excel и CSV', async ({ page, request }) => {
  const xlsx = await request.get('/api/games/4x20/export?format=xlsx')
  expect(xlsx.status()).toBe(200)
  expect(xlsx.headers()['content-type']).toContain('spreadsheetml')
  expect((await xlsx.body()).subarray(0, 2).toString()).toBe('PK')
  const draws = await request.get('/api/games/4x20/export?format=csv&what=draws')
  expect((await draws.text()).split('\n')[0]).toContain('Тираж;Дата;Поле 1;Поле 2')
  expect((await request.get('/api/games/duel/export?format=csv&what=journal')).status()).toBe(404)
  await page.goto('/games/4x20')
  await page.getByTestId('export-menu').click()
  const download = page.waitForEvent('download')
  await page.getByTestId('export-csv-journal').click()
  expect((await download).suggestedFilename()).toBe('4x20_journal.csv')
})

test('режим Бога, запущенный из консоли, виден в приложении', async ({ page }) => {
  const root = path.resolve(__dirname, '../..')
  const python = process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3')
  const lock = path.join(__dirname, '.data', 'results', '4x20', 'godmode.lock')
  const child = spawn(python, [path.join(root, 'python', 'lp.py'), 'godmode', '--game', '4x20', '--budget', '1'], {
    cwd: root, env: { ...process.env, LOTTERY_DATA_DIR: path.join(__dirname, '.data') }, stdio: 'ignore',
  })
  try {
    await expect.poll(() => fs.existsSync(lock), { timeout: 30_000 }).toBe(true)
    await page.goto('/games/4x20')
    await page.getByTestId('tab-god').click()
    await expect(page.getByTestId('god-progress')).toContainText('Запущено вне приложения', { timeout: 30_000 })
    await expect(page.getByTestId('god-result')).toContainText('Завершено', { timeout: 180_000 })
  } finally {
    child.kill()
  }
})

test('автозапуск: цикл из приложения', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('run-auto').click()
  await expect(page.getByTestId('auto-status')).toContainText('готово', { timeout: 240_000 })
  await page.goto('/games/4x20')
  await page.getByTestId('tab-journal').click()
  await expect(page.getByTestId('journal-entries')).toContainText('№13897')
})

test('устаревшая игра: анализ есть, в журнал не пишется', async ({ page }) => {
  await page.goto('/games/duel')
  await page.getByTestId('run-analysis').click()
  await expect(page.getByTestId('overview')).toBeVisible({ timeout: 120_000 })
  await page.getByTestId('tab-journal').click()
  await expect(page.getByTestId('journal')).toContainText('Журнал пуст')
})

test('бинго-игры: невыпавшие числа и первые шары', async ({ page }) => {
  await page.goto('/games/ruslotto')
  await page.getByTestId('run-analysis').click()
  await expect(page.getByTestId('overview')).toContainText('Невыпавшие числа: прогноз 11 из 1–90', { timeout: 120_000 })
  await page.getByTestId('tab-methods').click()
  await expect(page.getByTestId('methods-prediction').locator('.balls-lg .ball')).toHaveCount(11)

  await page.goto('/games/bingo75')
  await page.getByTestId('run-analysis').click()
  await expect(page.getByTestId('overview')).toContainText('Первые 10 шаров', { timeout: 120_000 })
  await expect(page.getByTestId('overview')).toContainText('Невыпавшие числа')
  await page.screenshot({ path: 'tests/e2e/.data/bingo.png', fullPage: true })
})

test('цифровая игра разбирается по позициям', async ({ page }) => {
  await page.goto('/games/top-3')
  await page.getByTestId('run-analysis').click()
  await expect(page.getByTestId('overview')).toContainText('Позиция 1: 1 из 0–9', { timeout: 120_000 })
})

test('API отклоняет некорректные запросы', async ({ request }) => {
  expect((await request.get('/api/games/..%2Fetc')).status()).toBe(404)
  expect((await request.get('/api/games/..%2Fetc/journal')).status()).toBe(400)
  expect((await request.post('/api/jobs', { data: { kind: 'rm', game: '4x20' } })).status()).toBe(400)
  expect((await request.post('/api/jobs', { data: { kind: 'godmode', game: '4x20', budget: 9999 } })).status()).toBe(400)
  expect((await request.post('/api/jobs', { data: { kind: 'analyze', game: '../x' } })).status()).toBe(400)
  expect((await request.get('/games/nope-game')).status()).toBe(404)
})
