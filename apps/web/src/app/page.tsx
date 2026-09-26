'use client'

import { useState, useEffect } from 'react'
import { startScan, listScans, type ScanRecord } from '@/lib/api'
import { TierBadge } from '@/components/ui/TierBadge'

export default function HomePage() {
  const [repo, setRepo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanningId, setScanningId] = useState<string | null>(null)
  const [recent, setRecent] = useState<ScanRecord[]>([])

  // Load recent scans on mount
  useEffect(() => {
    listScans().then(data => setRecent(data.scans ?? []))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = repo.trim()
    if (!trimmed || loading) return

    setLoading(true)
    setError(null)
    try {
      const scan = await startScan(trimmed)
      setScanningId(scan.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start scan')
      setLoading(false)
    }
  }

  if (scanningId) {
    return <ScanningPage id={scanningId} onDone={() => { setScanningId(null); setLoading(false) }} />
  }

  return (
    <main className="flex flex-col items-center justify-center min-h-[80vh] px-4">
      {/* Logo */}
      <div className="mb-6 text-6xl">🔥</div>
      <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-center">
        How <span className="text-orange-500">cooked</span> is your code?
      </h1>
      <p className="mt-3 text-lg text-gray-500 text-center max-w-xl">
        Scan any public GitHub repo for security issues, bugs, performance problems, and hygiene
        violations. Get a heat score in under a minute.
      </p>

      {/* Tier legend */}
      <div className="flex flex-wrap items-center gap-3 mt-8">
        {[
          { name: 'Raw',              color: '#2B6CC4' },
          { name: 'Lightly Toasted',  color: '#3D8B40' },
          { name: 'Medium Well',      color: '#C9922B' },
          { name: 'Cooked',           color: '#CF3626' },
          { name: 'Burnt to a Crisp', color: '#4A2A22' },
        ].map(t => (
          <span key={t.name} className="flex items-center gap-1.5 text-xs">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: t.color }} />
            {t.name}
          </span>
        ))}
      </div>

      {/* Input form */}
      <form onSubmit={handleSubmit} className="mt-10 w-full max-w-2xl">
        <div className="flex gap-2">
          <input
            type="text"
            value={repo}
            onChange={e => setRepo(e.target.value)}
            placeholder="owner/repo or https://github.com/owner/repo"
            className="flex-1 rounded-xl border border-gray-300 dark:border-surface-border bg-white dark:bg-surface-raised
                       px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50
                       placeholder:text-gray-400 dark:text-gray-100"
            disabled={loading}
            autoFocus
          />
          <button
            type="submit"
            disabled={loading || !repo.trim()}
            className="rounded-xl bg-orange-600 hover:bg-orange-500 disabled:opacity-40 disabled:cursor-not-allowed
                       px-6 py-3 text-sm font-semibold text-white transition-colors"
          >
            {loading ? 'Scanning…' : 'Scan'}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
      </form>

      {/* Recent scans */}
      {recent.length > 0 && (
        <div className="w-full max-w-2xl mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-4">
            Recent Scans
          </h2>
          <div className="space-y-2">
            {recent.slice(0, 8).map(scan => (
              <button
                key={scan.id}
                onClick={() => { setScanningId(scan.id); setError(null) }}
                className="w-full flex items-center gap-4 p-3 rounded-xl border border-gray-200 dark:border-surface-border
                           bg-white dark:bg-surface-raised hover:border-gray-300 dark:hover:border-surface-border
                           transition-colors text-left"
              >
                <span className="text-sm font-mono text-gray-600 dark:text-gray-400 truncate flex-1">
                  {scan.repo}
                </span>
                <TierBadge scan={scan} />
                <span className="text-xs text-gray-400">{scan.loc.toLocaleString()} LOC</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </main>
  )
}

function ScanningPage({ id, onDone }: { id: string; onDone: () => void }) {
  const [status, setStatus] = useState({ label: 'Queued' as string, progress: 0, message: 'Waiting…' })
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const es = new EventSource(`${apiBase}/api/scans/${id}/stream`)

    es.onmessage = (evt) => {
      const data = JSON.parse(evt.data)
      setStatus({
        label: data.status ?? 'scanning',
        progress: data.progress ?? status.progress,
        message: data.message ?? '',
      })
      if (data.status === 'complete') {
        es.close()
        setTimeout(() => { window.location.href = `/report/${id}` }, 600)
      }
      if (data.status === 'failed') {
        setError(data.error ?? 'Scan failed')
        es.close()
      }
    }
    return () => es.close()
  }, [id])

  return (
    <main className="flex flex-col items-center justify-center min-h-[80vh] px-4">
      <div className="text-6xl animate-pulse-soft">🔥</div>
      <h2 className="mt-6 text-2xl font-bold">{error ? 'Scan failed' : 'Scanning your repo…'}</h2>

      {/* Progress bar */}
      <div className="w-full max-w-xl mt-8">
        <div className="h-3 rounded-full bg-gray-200 dark:bg-surface-raised overflow-hidden">
          <div
            className="h-full rounded-full score-gradient progress-fill"
            style={{ width: `${Math.max(status.progress, 3)}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span>{status.message}</span>
          <span>{status.progress}%</span>
        </div>
      </div>

      {error && (
        <div className="mt-6 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 px-4 py-3 text-sm text-red-700 max-w-xl w-full">
          {error}
        </div>
      )}

      <button
        onClick={onDone}
        className="mt-8 text-sm text-gray-500 hover:text-gray-300 transition-colors"
      >
        ← Back to home
      </button>
    </main>
  )
}
