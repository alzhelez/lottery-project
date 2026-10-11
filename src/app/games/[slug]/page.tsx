import { notFound } from 'next/navigation'
import { GameView } from '@/components/GameView'
import { readGameInfo } from '@/lib/games'

export const dynamic = 'force-dynamic'

export default async function GamePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const info = readGameInfo(slug)
  if (!info) notFound()
  return <GameView info={info} />
}
