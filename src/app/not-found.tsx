import Link from 'next/link'

export default function NotFound() {
  return (
    <main className="page">
      <h1>Такой игры нет</h1>
      <p>Проверьте адрес или выберите игру <Link href="/">в списке</Link>.</p>
    </main>
  )
}
