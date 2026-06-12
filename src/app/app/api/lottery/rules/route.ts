import { NextResponse } from 'next/server'
import { validateGameId } from '@/lib/api-utils'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { game } = body

    const gameErr = validateGameId(game)
    if (gameErr) {
      return NextResponse.json({ error: gameErr }, { status: 400 })
    }

    if (!game) {
      return NextResponse.json(
        { error: 'Missing game parameter in request body' },
        { status: 400 }
      )
    }

    const url = `https://www.stoloto.ru/${game}/rules`

    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': `https://www.stoloto.ru/${game}`,
      },
      signal: AbortSignal.timeout(15000), // 15 second timeout
    })

    if (!res.ok) {
      return NextResponse.json({
        error: `Failed to fetch rules: HTTP ${res.status}`,
        status: 'error',
      }, { status: 502 })
    }

    const html = await res.text()

    // Extract text content (basic HTML stripping)
    const text = html
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#(\d+);/g, (_, n: string) => String.fromCharCode(parseInt(n, 10)))
      .replace(/\s+/g, ' ')
      .trim()

    // Try to extract rules sections (look for heading patterns)
    const rulesSections: { title: string; content: string }[] = []
    const sectionRegex = /<h[2-4][^>]*>([^<]+)<\/h[2-4]>/gi
    let match: RegExpExecArray | null
    const headings: { title: string; index: number }[] = []

    // First pass: collect all headings with their positions
    while ((match = sectionRegex.exec(html)) !== null) {
      headings.push({ title: match[1].trim(), index: match.index })
    }

    // Second pass: extract content between headings
    for (let i = 0; i < headings.length; i++) {
      const heading = headings[i]
      const startIdx = heading.index + html.indexOf('>', heading.index) + 1
      const endIdx = i + 1 < headings.length
        ? headings[i + 1].index
        : startIdx + 3000

      const rawContent = html.substring(startIdx, endIdx)
      const contentText = rawContent
        .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
        .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#(\d+);/g, (_: string, n: string) => String.fromCharCode(parseInt(n, 10)))
        .replace(/\s+/g, ' ')
        .trim()

      // Skip empty or very short sections
      if (contentText.length > 10) {
        rulesSections.push({
          title: heading.title,
          content: contentText.substring(0, 500),
        })
      }
    }

    // If no sections found, try extracting from main content area
    const mainContent = html.match(/<main[^>]*>([\s\S]*?)<\/main>/i) ||
      html.match(/<div[^>]*class="[^"]*rules[^"]*"[^>]*>([\s\S]*?)<\/div>/i) ||
      html.match(/<div[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)<\/div>/i)

    let extractedText = text.substring(0, 5000)

    if (mainContent) {
      const mainText = mainContent[1]
        .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
        .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#(\d+);/g, (_: string, n: string) => String.fromCharCode(parseInt(n, 10)))
        .replace(/\s+/g, ' ')
        .trim()
      if (mainText.length > extractedText.length) {
        extractedText = mainText.substring(0, 5000)
      }
    }

    return NextResponse.json({
      game,
      rules_text: extractedText,
      sections: rulesSections.slice(0, 20),
      status: 'ok',
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'

    // Handle timeout gracefully
    if (message.includes('timeout') || message.includes('Timeout') || message.includes('aborted')) {
      return NextResponse.json({
        error: 'Request to stoloto.ru timed out',
        status: 'timeout',
      })
    }

    return NextResponse.json(
      { error: message, status: 'error' },
      { status: 500 }
    )
  }
}
