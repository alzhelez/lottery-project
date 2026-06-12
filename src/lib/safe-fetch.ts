/**
 * Safe fetch helper that ensures we always get JSON (never HTML).
 *
 * The "Unexpected token '<'" error occurs when a Next.js API route crashes
 * and returns an HTML error page instead of JSON. This helper:
 *  1. Checks Content-Type before parsing
 *  2. Returns a structured error object instead of throwing
 *  3. Wraps the response in a { ok, data, status } envelope
 *  4. Supports custom timeout via AbortController
 */

export interface SafeFetchResult<T = unknown> {
  ok: boolean
  data: T | null
  status: number
  error?: string
}

export interface SafeFetchOptions extends RequestInit {
  /** Custom timeout in ms (default: no timeout — relies on server) */
  timeoutMs?: number
}

export async function safeFetch<T = unknown>(
  url: string,
  options?: SafeFetchOptions,
): Promise<SafeFetchResult<T>> {
  const { timeoutMs, ...fetchOptions } = options || {}
  let controller: AbortController | undefined

  try {
    // Set up timeout if requested
    if (timeoutMs && timeoutMs > 0) {
      controller = new AbortController()
      fetchOptions.signal = controller.signal
      setTimeout(() => controller?.abort(), timeoutMs)
    }

    const res = await fetch(url, fetchOptions)

    // Check content type — reject HTML responses
    const contentType = res.headers.get('content-type') || ''
    const isJson = contentType.includes('application/json')

    if (!isJson) {
      // Read body as text for diagnostics
      const text = await res.text().catch(() => '')
      const preview = text.substring(0, 200).replace(/[\r\n]+/g, ' ')
      console.error(`[safeFetch] Non-JSON response from ${url}: status=${res.status}, type=${contentType}, body=${preview}`)

      let errorHint = `Сервер вернул не JSON (status ${res.status}). Попробуйте позже.`
      if (res.status === 504) {
        errorHint = 'Сервер не успел обработать запрос (таймаут). Нажмите «Обновить» — при повторном запросе будет использован кеш предыдущего анализа.'
      } else if (res.status === 502) {
        errorHint = 'Сервер временно недоступен. Подождите минуту и попробуйте снова.'
      }

      return {
        ok: false,
        data: null,
        status: res.status,
        error: errorHint,
      }
    }

    const data = await res.json() as T
    return { ok: res.ok, data, status: res.status }
  } catch (err) {
    const message = err instanceof Error
      ? (err.name === 'AbortError' ? 'Превышено время ожидания. Попробуйте снова.' : err.message)
      : 'Ошибка сети'
    console.error(`[safeFetch] Error fetching ${url}:`, message)
    return {
      ok: false,
      data: null,
      status: 0,
      error: message,
    }
  }
}
