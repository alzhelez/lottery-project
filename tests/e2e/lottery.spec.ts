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
  for (const slug of ['6x45plus', 'top-3', 'duel']) {
    await expect(page.getByTestId(`fetch-${slug}`)).toContainText('Готово')
  }
  // бинго (числа не выбираются) убраны из программы: не загружаются, хотя API их отдаёт
  for (const slug of ['ruslotto', 'bingo75']) await expect(page.getByTestId(`fetch-${slug}`)).toHaveCount(0)
  await expect(page.getByTestId('fetch-5x36')).toContainText('Нет архива')
  await expect(page.getByTestId('fetch-4x20')).toContainText('1 499')
  await expect(page.getByTestId('scan-status')).toContainText('завершена', { timeout: 120_000 })
  await page.getByRole('button', { name: 'Закрыть окно' }).click()

  const table = page.getByTestId('games-table')
  await expect(table.getByTestId('row-4x20')).toContainText('1 499')
  await expect(table.getByTestId('row-4x20')).toContainText('№13896')
  for (const slug of ['4x20', '6x45plus', 'top-3']) {
    await expect(table.getByTestId(`row-${slug}`)).not.toContainText('не проверялась')
  }
  await expect(table.getByTestId('row-ruslotto')).toHaveCount(0)
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
  // в таблице сначала 10 лучших методов — контроль может оказаться ниже
  await page.getByRole('button', { name: /Показать все методы/ }).click()
  await expect(page.getByTestId('models-table')).toContainText('Случайный выбор (контроль)')
  await expect(page.getByTestId('method-edge')).toContainText('Что исключено')
  await expect(page.getByTestId('methods-by-mechanism')).toContainText('лототрон')
  await page.getByTestId('tab-overview').click()
  // лототрон в ровный час (есть видео), ГСЧ — «с секундами»: в моке 4 из 10 слотов — ровный час
  await expect(page.getByTestId('mechanisms')).toContainText('Лототрон — 600 тиражей')
  await expect(page.getByTestId('mechanisms')).toContainText('ГСЧ — 899 тиражей')
  await expect(page.getByTestId('detectable')).toContainText('чаще нормы')
  await expect(page.getByTestId('drift')).toContainText('Дрейфа нет')
  await expect(page.getByTestId('repeats')).toContainText('Повторы по позициям выпадения')
  await expect(page.getByTestId('repeats')).toContainText('Сдвинутое число на сдвинутой позиции')
  // порядок из хаоса: лототрон и ГСЧ — отдельные наборы тиражей
  await page.getByTestId('tab-chaos').click()
  await expect(page.getByTestId('chaos-conclusion')).toContainText('Лототрон (600 тиражей)')
  await expect(page.getByTestId('chaos-conclusion')).toContainText('ГСЧ (899 тиражей)')
  await expect(page.getByTestId('chaos-prediction')).toContainText('Прогноз на тираж №13896')
  await expect(page.getByTestId('chaos-group-R')).toContainText('порядка нет')
  await expect(page.getByTestId('chaos-checks-L')).toContainText('Нелинейная предсказуемость')
  await expect(page.getByTestId('chaos-methods-R')).toContainText('Аналоги последнего тиража')
  await page.getByText('Как это устроено').click()
  await expect(page.getByTestId('chaos-about')).toContainText('Такенса')
  await page.screenshot({ path: 'tests/e2e/.data/chaos.png', fullPage: true })
})

test('правила игры со stoloto.ru и ожидаемый возврат ближайшего тиража', async ({ page }) => {
  await page.goto('/games/4x20')
  await page.getByTestId('tab-rules').click()
  const rules = page.getByTestId('rules')
  await expect(rules).toContainText('10:00 (лототрон)')
  await expect(page.getByTestId('rules-mechanism')).toContainText('лототрон и генератор случайных чисел')
  await expect(page.getByTestId('rules-table')).toContainText('Суперприз')
  await expect(page.getByTestId('rules-table')).toContainText('4 + 3')
  await expect(page.getByTestId('rules-superprize')).toContainText('300 000 000 ₽')
  await expect(page.getByTestId('rules-return')).toHaveText(/\d,\d+/)
  await page.getByTestId('tab-odds').click()
  await expect(page.getByTestId('next-draw-return')).toContainText('Ближайший тираж №13896')
})

test('режим Бога: запуск, промежуточный и итоговый результат', async ({ page }) => {
  await page.goto('/games/4x20')
  await page.getByTestId('tab-god').click()
  // поля бюджета нет: режим работает до исчерпания перебора (не дольше 8 часов)
  await expect(page.getByTestId('budget')).toHaveCount(0)
  await page.getByTestId('run-god').click()
  await expect(page.getByTestId('god-progress')).toBeVisible()
  await expect(page.getByTestId('run-god')).toBeVisible({ timeout: 400_000 })
  const result = page.getByTestId('god-result')
  await expect(result).toContainText('Завершено: перебор исчерпан')
  await expect(result).toContainText('Стратегия «Лидер за всю историю»')
  await expect(result).toContainText('Прогноз на тираж №13896')
  await expect(page.getByTestId('timeline').locator('tbody tr')).toHaveCount(30)
})

test('журнал прогнозов: запись до тиража и сверка после загрузки', async ({ page, request }) => {
  await page.goto('/games/4x20')
  await page.getByTestId('tab-journal').click()
  const entries = page.getByTestId('journal-entries')
  // «Все»: одна строка на тираж, по нажатию — прогнозы четырёх источников
  await expect(page.getByTestId('journal-draw')).toHaveCount(1)
  await expect(entries).toContainText('ждёт тиража')
  await expect(entries).toContainText('№13896')
  await expect(entries).toContainText('4 источника')
  await page.getByTestId('journal-draw').click()
  await expect(page.getByTestId('journal-source-row')).toHaveCount(4)
  await expect(entries).toContainText('Порядок из хаоса')
  await page.getByTestId('journal-draw').click()
  await expect(page.getByTestId('journal-source-row')).toHaveCount(0)
  await page.getByRole('button', { name: 'Порядок из хаоса' }).click()
  await expect(entries.locator('tbody tr')).toHaveCount(1)
  await page.getByRole('button', { name: 'Все', exact: true }).click()

  // тираж №13896 «состоялся» — загружаем его
  expect((await (await request.get(`${MOCK}/__release`)).json()).released).toEqual([13896])
  const job = await runJob(request, { kind: 'fetch', game: '4x20' })
  expect(job.status).toBe('done')
  expect(job.games['4x20'].journal_checked).toBe(4)

  await page.reload()
  await page.getByTestId('tab-journal').click()
  await expect(entries).toContainText('сверен')
  await expect(entries).not.toContainText('ждёт тиража')
  await page.getByTestId('journal-draw').click()
  await expect(page.getByTestId('journal-source-row').filter({ hasText: 'сверен' })).toHaveCount(4)
  const summary = page.getByTestId('journal-summary')
  for (const title of ['Лучший метод анализа', 'Консенсус методов', 'Режим Бога', 'Порядок из хаоса']) {
    await expect(summary.locator('tr', { hasText: title }).locator('td').nth(1)).toHaveText('1')
  }
  await page.screenshot({ path: 'tests/e2e/.data/journal.png', fullPage: true })
})

test('итоги прогнозов по всем играм', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Итоги прогнозов' }).click()
  const summary = page.getByTestId('overview-summary')
  for (const title of ['Лучший метод анализа', 'Консенсус методов', 'Порядок из хаоса', 'Режим Бога']) {
    await expect(summary.locator('tr', { hasText: title }).locator('td').nth(1)).toHaveText('1')
  }
  await expect(summary).toContainText('в пределах случайности')
  await expect(page.getByTestId('curve-chaos')).toBeVisible()
  await expect(page.getByTestId('overview-games')).toContainText('4 из 20')
  await page.screenshot({ path: 'tests/e2e/.data/overview.png', fullPage: true })
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
})

test('мои билеты: внесение, сверка с тиражом и денежный итог', async ({ page, request }) => {
  const games = (await (await request.get('/api/games')).json()).games as Array<{ slug: string; last: { no: number } }>
  const last = games.find((g) => g.slug === '4x20')!.last.no
  // билет на уже сыгранный тираж сверяется сразу
  const r = await request.post('/api/my-tickets', { data: { game: '4x20', numbers: '1,2,3,4|5,6,7,8', draw_no: last, price: 150 } })
  expect(r.status()).toBe(200)
  const [checked] = (await r.json()).added
  expect(checked.status).toBe('checked')
  expect(checked.hits_by_block).toHaveLength(2)
  expect((await request.post('/api/my-tickets', { data: { game: '4x20', numbers: '1,2,3' } })).status()).toBe(400)
  expect((await request.post('/api/my-tickets', { data: { game: '../x', numbers: '1' } })).status()).toBe(400)

  // на странице игры — вкладка «Мои билеты»: билет на два ближайших тиража
  await page.goto('/games/4x20')
  await page.getByTestId('tab-mine').click()
  await expect(page.getByTestId('mt-row')).toHaveCount(1)
  await page.getByTestId('mt-numbers').fill('3, 11, 17, 20 | 2, 9, 14, 19')
  await page.getByTestId('mt-draws').fill('2')
  await page.getByTestId('mt-add').click()
  await expect(page.getByTestId('mt-added')).toContainText(`тиражи №${last + 1}–${last + 2}`)
  await expect(page.getByTestId('mt-row')).toHaveCount(3)
  await expect(page.getByTestId('mt-row').filter({ hasText: 'ждёт тиража' })).toHaveCount(2)

  // общая страница: итог по всем играм, выигрыш вручную, удаление
  await page.goto('/my-tickets')
  await expect(page.getByTestId('mytickets-summary')).toContainText('сверено 1, ждут тиража 2')
  await expect(page.getByTestId('mt-spent')).toContainText('150')
  const row = page.getByTestId('mt-row').filter({ hasText: `№${last}` })
  await row.getByRole('button', { name: 'вписать' }).click()
  await row.getByTestId('mt-won-input').fill('1000')
  await row.getByRole('button', { name: 'сохранить' }).click()
  await expect(page.getByTestId('mt-won')).toContainText('1 000')
  await expect(page.getByTestId('mt-balance')).toContainText('+850')
  await page.getByTestId('mt-row').filter({ hasText: 'ждёт тиража' }).first().getByTestId('mt-delete').click()
  await expect(page.getByTestId('mt-row')).toHaveCount(2)
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
  await expect(page.getByTestId('auto-status')).toContainText('готово', { timeout: 400_000 })
  // цикл сделал резервную копию журнала и билетов
  await expect(page.getByTestId('backup-status')).toContainText('последняя')
  await page.goto('/games/4x20')
  await page.getByTestId('tab-journal').click()
  await expect(page.getByTestId('journal-entries')).toContainText('№13897')
  // в автозапуске у игры есть прогнозы всех четырёх источников, включая режим Бога
  await page.getByTestId('journal-draw').filter({ hasText: '№13897' }).click()
  await expect(page.getByTestId('journal-source-row')).toHaveCount(4)
})

test('устаревшая игра: анализ есть, в журнал не пишется', async ({ page }) => {
  await page.goto('/games/duel')
  await page.getByTestId('run-analysis').click()
  await expect(page.getByTestId('overview')).toBeVisible({ timeout: 120_000 })
  await page.getByTestId('tab-journal').click()
  await expect(page.getByTestId('journal')).toContainText('Журнал пуст')
})

test('игры без выбора чисел убраны из программы', async ({ page }) => {
  // бинго: числа в билете напечатаны заранее — страницы игры нет
  const res = await page.goto('/games/ruslotto')
  expect(res?.status()).toBe(404)
  await page.goto('/odds')
  await expect(page.getByText('Русское лото')).toHaveCount(0)
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
