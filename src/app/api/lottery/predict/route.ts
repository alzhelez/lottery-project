import { createCachedOperationHandler } from '@/lib/background-cache'

const handlePredict = createCachedOperationHandler({
  operationLabel: 'predict',
  scriptName: 'predict.py',
  scriptArgs: (_game, _file, extra) => {
    const enableCv = extra?.enable_cv !== true
    const args = ['--file', _file]
    if (enableCv) args.push('--no-cv')
    args.push('--batch-step', '50', '--full-every', '3')
    return args
  },
  timeoutMs: 600000,
})

export async function POST(request: Request) {
  return handlePredict(request) as ReturnType<typeof handlePredict>
}
