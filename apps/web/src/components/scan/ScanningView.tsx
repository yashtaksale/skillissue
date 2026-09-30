'use client'

import { useState, useEffect } from 'react'

interface ScanningViewProps {
  id: string
  onDone: () => void
}

export function ScanningView({ id, onDone }: ScanningViewProps) {
  const [status, setStatus] = useState({ label: 'Queued', progress: 5, message: 'Initializing secure analysis pipeline...' })
  const [error, setError] = useState<string | null>(null)
  const [logLines, setLogLines] = useState<string[]>([
    'Establishing secure connection to analysis engine...',
  ])

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'
    const es = new EventSource(`${apiBase}/api/scans/${id}/stream`)

    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        const msg = data.message ?? 'Analyzing code...'

        setStatus({
          label: data.status ?? 'scanning',
          progress: data.progress ?? status.progress,
          message: msg,
        })

        if (msg) {
          setLogLines(prev => [...prev.slice(-9), `[${new Date().toISOString().split('T')[1].substring(0, 8)}] ${msg}`])
        }

        if (data.status === 'complete') {
          es.close()
          setTimeout(() => { window.location.href = `/report/${id}` }, 600)
        }

        if (data.status === 'failed') {
          setError(data.error ?? 'Analysis pipeline encountered a critical error')
          es.close()
        }
      } catch (e) {}
    }

    return () => es.close()
  }, [id])

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 font-sans bg-zinc-950">
      <div className="w-full max-w-lg glass-panel p-8 sm:p-10 text-center space-y-8">

        {/* Minimal Loader */}
        <div className="relative w-32 h-32 mx-auto flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border border-white/5" />
          <div className="absolute inset-0 rounded-full border-t-2 border-white animate-spin" style={{ animationDuration: '2s' }} />
          <div className="absolute inset-2 rounded-full border border-white/5" />

          <div className="w-16 h-16 rounded-full bg-zinc-900 flex items-center justify-center">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-white tracking-tight animate-pulse">ANALYZING CODEBASE</h2>
          <p className="text-sm text-zinc-400 mt-2 font-mono">{status.message}</p>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs text-zinc-500 font-mono font-medium">
            <span>Pipeline Progress</span>
            <span className="text-white">{status.progress}%</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
            <div
              className="h-full bg-white transition-all duration-500 ease-out relative"
              style={{ width: `${Math.max(status.progress, 5)}%` }}
            >
            </div>
          </div>
        </div>

        {/* Live Terminal Log Stream */}
        <div className="w-full bg-[#08080a] rounded-xl p-4 border border-white/5 text-left font-mono text-[11px] leading-relaxed text-zinc-500 space-y-1 h-40 overflow-hidden shadow-inner flex flex-col justify-end">
          {logLines.map((line, idx) => (
            <div key={idx} className="flex items-start gap-2 opacity-80">
              <span className="text-zinc-600 font-bold">❯</span>
              <span className="break-all">{line}</span>
            </div>
          ))}
          <div className="flex items-center gap-2 mt-1">
            <span className="text-white font-bold">❯</span>
            <span className="w-2 h-3 bg-white/80 animate-pulse" />
          </div>
        </div>

        {error && (
          <div className="text-sm text-red-400 mt-4 p-4 rounded-xl bg-red-400/5 border border-red-400/10 text-left">
            <p className="font-bold flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              Analysis Failed
            </p>
            <p className="mt-1 opacity-90">{error}</p>
            <button onClick={onDone} className="mt-3 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white text-xs font-semibold transition-colors border border-white/10">
              Return Home
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
