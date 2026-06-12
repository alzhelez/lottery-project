import { createCachedOperationHandler } from '@/lib/background-cache'

const handlePipeline = createCachedOperationHandler({
  operationLabel: 'pipeline',
  scriptName: 'pipeline.py',
  scriptArgs: (game) => ['--game', game],
  timeoutMs: 600000,
})

export async function POST(request: Request) {
  return handlePipeline(request) as ReturnType<typeof handlePipeline>
}
