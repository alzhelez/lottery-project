'use server'

import { NextResponse } from 'next/server'
import { errorJson } from '@/lib/api-utils'
import { rateLimit } from '@/lib/rate-limit'
import ZAI from 'z-ai-web-dev-sdk'

// ── Rate limit ─────────────────────────────────────────────────────────────────

const EXPLAIN_RATE_MAX = 5
const EXPLAIN_RATE_WINDOW_MS = 60 * 1000 // 1 minute

// ── System prompt ──────────────────────────────────────────────────────────────

const SYSTEM_PROMPT = `Ты — эксперт-аналитик лотерейных прогнозов. Твоя задача — объяснить пользователю на русском языке, почему именно эти числа были выбраны как итоговое предсказание.

Правила:
- Отвечай только на русском языке
- Будь конкретным и опирайся на статистику
- Объясни частоту появления каждого числа, уровень согласия моделей
- Упомяни strongest и weakest стороны прогноза
- Не давай финансовых советов
- Формат: структурированный текст с заголовками и списками, используй эмодзи для визуализации
- Не придумывай данные — используй только то, что предоставлено
- Объём ответа: 300-500 слов`

// ── POST handler ──────────────────────────────────────────────────────────────

export async function POST(request: Request) {
  try {
    // Rate limit
    const rl = rateLimit('godmode-explain', EXPLAIN_RATE_MAX, EXPLAIN_RATE_WINDOW_MS)
    if (!rl.allowed) {
      return errorJson(
        `Слишком много запросов. Подождите ${Math.ceil(rl.resetIn / 1000)}с.`,
        429,
        { retry_after: Math.ceil(rl.resetIn / 1000) },
      )
    }

    const body = await request.json()
    const {
      game_name,
      game_format,
      total_draws,
      next_draw_number,
      runs_total,
      runs_successful,
      avg_consensus_b1,
      avg_consensus_b2,
      prediction_b1,
      prediction_b2,
      top_numbers_b1,
      top_numbers_b2,
      best_run_consensus_b1,
      best_run_consensus_b2,
    } = body

    // Validate required fields
    if (!game_name || !game_format || !prediction_b1 || !prediction_b2) {
      return errorJson('Missing required fields: game_name, game_format, prediction_b1, prediction_b2', 400)
    }

    // Build data summary for the prompt
    const topB1Str = (top_numbers_b1 || [])
      .slice(0, 10)
      .map((item: { number: string; count: number }) => `  ${item.number}: ${item.count} раз из ${runs_successful || runs_total}`)
      .join('\n')

    const topB2Str = (top_numbers_b2 || [])
      .slice(0, 10)
      .map((item: { number: string; count: number }) => `  ${item.number}: ${item.count} раз из ${runs_successful || runs_total}`)
      .join('\n')

    const userPrompt = `Проанализируй результаты мультизапуска прогнозирования и объясни, почему именно эти числа выбраны.

**Игра**: ${game_name}
**Формат**: ${game_format}
**Всего тиражей в базе**: ${total_draws || 'неизвестно'}
**Прогноз на тираж №**: ${next_draw_number || '?'}

**Статистика запусков**:
- Всего запусков: ${runs_total || '?'}
- Успешных: ${runs_successful || runs_total || '?'}
- Среднее согласие Блок 1: ${avg_consensus_b1 != null ? (avg_consensus_b1 * 100).toFixed(1) + '%' : 'нет данных'}
- Среднее согласие Блок 2: ${avg_consensus_b2 != null ? (avg_consensus_b2 * 100).toFixed(1) + '%' : 'нет данных'}
- Лучший запуск согласие: Б1=${best_run_consensus_b1 != null ? (best_run_consensus_b1 * 100).toFixed(1) + '%' : '?'}, Б2=${best_run_consensus_b2 != null ? (best_run_consensus_b2 * 100).toFixed(1) + '%' : '?'}

**Итоговое предсказание**:
- Блок 1: ${prediction_b1.join(', ')}
- Блок 2: ${prediction_b2.join(', ')}

**Частота чисел в запусках (Блок 1)**:
${topB1Str || '  нет данных'}

**Частота чисел в запусках (Блок 2)**:
${topB2Str || '  нет данных'}

Объясни выбор каждого числа, опираясь на статистику частоты и уровень согласия моделей. Подчеркни наиболее надёжные числа и укажи на любые сомнения или риски.`

    // Call LLM
    const zai = await ZAI.create()
    const completion = await zai.chat.completions.create({
      messages: [
        { role: 'assistant', content: SYSTEM_PROMPT },
        { role: 'user', content: userPrompt },
      ],
      thinking: { type: 'disabled' },
    })

    const explanation = completion.choices[0]?.message?.content

    if (!explanation || explanation.trim().length === 0) {
      return errorJson('Не удалось сгенерировать объяснение. Попробуйте ещё раз.', 500)
    }

    return NextResponse.json({
      status: 'ok',
      explanation,
    })
  } catch (error) {
    console.error('[god-mode/explain] Error:', error)
    return errorJson(
      error instanceof Error ? error.message : 'Ошибка генерации объяснения',
      500,
    )
  }
}
