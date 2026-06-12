interface SafeFetchResult<T = Record<string, unknown>> {
  data: T
  ok: boolean
}

function isTimeoutError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'TimeoutError'
    || err instanceof Error && err.message.includes('timeout')
    || err instanceof Error && err.message.includes('abort')
}

export async function safeJsonFetch<T = Record<string, unknown>>(
  url: string,
  options?: RequestInit,
  timeoutMs?: number,
): Promise<SafeFetchResult<T>> {
  let timer: ReturnType<typeof setTimeout> | undefined
  let mergedOptions: RequestInit = options || {}
  if (timeoutMs && timeoutMs > 0) {
    const ac = new AbortController()
    timer = setTimeout(() => ac.abort(new DOMException('Timeout', 'TimeoutError')), timeoutMs)
    mergedOptions = { ...options, signal: ac.signal }
  }

  try {
    const res = await fetch(url, mergedOptions)
    const contentType = res.headers.get('content-type') || ''

    if (!res.ok) {
      if (contentType.includes('application/json')) {
        const body = await res.json().catch(() => null)
        if (body?.error) {
          return { data: body as T, ok: false }
        }
      }
      const text = await res.text().catch(() => '')
      const isHtml = text.trimStart().startsWith('<')
      if (isHtml) {
        return { data: { error: `Сервер вернул ошибку (HTTP ${res.status}). Попробуйте снова.` } as T, ok: false }
      }
      return { data: { error: `Ошибка HTTP ${res.status}: ${text.slice(0, 200)}` } as T, ok: false }
    }

    if (!contentType.includes('application/json')) {
      const text = await res.text().catch(() => '')
      try {
        return { data: JSON.parse(text) as T, ok: true }
      } catch {
        const isHtml = text.trimStart().startsWith('<')
        if (isHtml) {
          return { data: { error: `Сервер вернул HTML вместо JSON (HTTP ${res.status}). Попробуйте снова.` } as T, ok: false }
        }
        return { data: { error: `Сервер вернул не-JSON ответ (HTTP ${res.status})` } as T, ok: false }
      }
    }

    const data = await res.json()
    return { data, ok: true }
  } catch (err) {
    if (isTimeoutError(err)) {
      return { data: { error: 'Превышено время ожидания запроса. Попробуйте снова.' } as T, ok: false }
    }
    return { data: { error: err instanceof Error ? err.message : 'Ошибка сети. Проверьте подключение.' } as T, ok: false }
  } finally {
    if (timer) clearTimeout(timer)
  }
}
