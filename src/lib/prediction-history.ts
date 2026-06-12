export interface SavedPrediction {
  id: string
  timestamp: number
  gameKey: string
  gameName: string
  prediction: {
    block1: number[]
    block2: number[]
  }
  confidence: {
    block1: number
    block2: number
    overall: number
  } | null
  modelsUsed: number
  consensusStrength: {
    block1: number
    block2: number
  } | null
  accuracyData: {
    last50avg: number | null
    last100avg: number | null
    improvementPct: number | null
  } | null
}

const STORAGE_KEY = 'lp_prediction_history'
const MAX_ENTRIES = 50

function readFromStorage(): SavedPrediction[] {
  try {
    if (typeof window === 'undefined') return []
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed as SavedPrediction[]
  } catch {
    return []
  }
}

function writeToStorage(predictions: SavedPrediction[]): void {
  try {
    if (typeof window === 'undefined') return
    localStorage.setItem(STORAGE_KEY, JSON.stringify(predictions))
  } catch {
    // Quota exceeded, private browsing, etc. — silently fail.
  }
}

export function getPredictionHistory(): SavedPrediction[] {
  return readFromStorage().sort((a, b) => b.timestamp - a.timestamp)
}

export function savePrediction(
  data: Omit<SavedPrediction, 'id' | 'timestamp'>,
): SavedPrediction {
  const entry: SavedPrediction = {
    ...data,
    id: crypto.randomUUID(),
    timestamp: Date.now(),
  }

  const history = readFromStorage()
  history.unshift(entry)

  if (history.length > MAX_ENTRIES) {
    // Trim oldest entries — history is oldest-first after unshift, so pop the tail.
    history.length = MAX_ENTRIES
  }

  writeToStorage(history)
  return entry
}

export function clearPredictionHistory(): void {
  try {
    if (typeof window === 'undefined') return
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Silently fail.
  }
}

export function deletePrediction(id: string): void {
  const history = readFromStorage()
  const filtered = history.filter((entry) => entry.id !== id)
  if (filtered.length !== history.length) {
    writeToStorage(filtered)
  }
}
