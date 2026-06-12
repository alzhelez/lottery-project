import { NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import { join } from 'path'

export async function GET() {
  try {
    const filePath = join(process.cwd(), 'upload', 'lottery_pipeline.py')
    const fileBuffer = await readFile(filePath)
    const fileContent = fileBuffer.toString('utf-8')

    return new NextResponse(fileContent, {
      headers: {
        'Content-Type': 'text/x-python;charset=utf-8',
        'Content-Disposition': 'attachment; filename="lottery_pipeline.py"',
        'Content-Length': Buffer.byteLength(fileContent, 'utf-8').toString(),
      },
    })
  } catch {
    return NextResponse.json(
      { error: 'File not found' },
      { status: 404 }
    )
  }
}
