import { createCachedOperationHandler } from '@/lib/background-cache'

const handleStepAnalysis = createCachedOperationHandler({
  operationLabel: 'step-analysis',
  scriptName: 'step_analysis.py',
  cacheKeyFields: ['steps'],
  scriptArgs: (_game, _file, extra) => {
    const steps = typeof extra?.steps === 'number' ? Math.max(1, Math.min(10, extra.steps)) : 5
    const fromDraw = typeof extra?.from_draw === 'number' ? extra.from_draw : null
    const toDraw = typeof extra?.to_draw === 'number' ? extra.to_draw : null
    const args = ['--file', _file, '--steps', String(steps)]
    if (fromDraw != null) args.push('--from-draw', String(fromDraw))
    if (toDraw != null) args.push('--to-draw', String(toDraw))
    return args
  },
  timeoutMs: 600000,
})

export async function POST(request: Request) {
  return handleStepAnalysis(request) as ReturnType<typeof handleStepAnalysis>
}
