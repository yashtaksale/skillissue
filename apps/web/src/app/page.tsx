'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { startScan, listScans, type ScanRecord } from '@/lib/api'
import { TierBadge } from '@/components/ui/TierBadge'
import { ScanningView } from '@/components/scan/ScanningView'

export default function HomePage() {
  const [repo, setRepo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanningId, setScanningId] = useState<string | null>(null)
  const [recent, setRecent] = useState<ScanRecord[]>([])

  useEffect(() => {
    listScans().then(data => setRecent(data.scans ?? [])).catch(() => {})
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    let trimmed = repo.trim()
    if (!trimmed || loading) return

    // Extract owner/repo if user pasted a full GitHub URL
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      try {
        const url = new URL(trimmed)
        if (url.hostname.includes('github.com')) {
          const parts = url.pathname.split('/').filter(Boolean)
          if (parts.length >= 2) {
            trimmed = `${parts[0]}/${parts[1]}`
            setRepo(trimmed)
          }
        }
      } catch (e) {
        // Ignore URL parsing errors, let backend validate
      }
    }

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
    return <ScanningView id={scanningId} onDone={() => { setScanningId(null); setLoading(false) }} />
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-between px-6 py-10 max-w-5xl mx-auto bg-zinc-950">
      {/* Top Navbar Header */}
      <header className="w-full flex items-center justify-between py-4 mb-16 animate-slide-up">
        <Link href="/" className="flex items-center gap-3 font-semibold text-2xl tracking-tight cursor-pointer hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center">
            <span className="text-white text-sm font-mono">SI</span>
          </div>
          <span>SkillIssue</span>
        </Link>
        <span className="text-xs font-mono text-zinc-500 border border-white/10 bg-white/5 px-3 py-1.5 rounded-full">v2.0</span>
      </header>

      {/* Main Hero Container */}
      <div className="w-full flex flex-col items-center text-center my-auto relative z-10 flex-1">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs font-mono text-zinc-300 mb-8 animate-slide-up stagger-1 backdrop-blur-sm">
          <span className="text-white">✦</span> Autonomous Code Security Analysis
        </div>

        <h1 className="text-5xl sm:text-7xl font-black tracking-tight leading-tight animate-slide-up stagger-2 max-w-4xl">
          Identify Vulnerabilities Before They <br className="hidden sm:block" />
          <span className="text-zinc-500">Reach Production.</span>
        </h1>

        <p className="mt-6 text-base sm:text-lg text-zinc-400 max-w-2xl font-sans leading-relaxed animate-slide-up stagger-3">
          Perform deep-dive static analysis, hygiene checks, and security audits on any GitHub repository in seconds. Actionable insights, zero configuration.
        </p>

        {/* Interactive Minimal Form */}
        <form onSubmit={handleSubmit} className="mt-12 w-full max-w-2xl animate-slide-up stagger-4 relative">
          <div className="relative group">
            <div className="relative flex flex-col sm:flex-row gap-3 p-2 rounded-2xl glass-panel">
              <div className="flex-1 relative">
                <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                  <svg className="w-5 h-5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                  </svg>
                </div>
                <input
                  type="text"
                  value={repo}
                  onChange={e => setRepo(e.target.value)}
                  placeholder="owner/repo (e.g. facebook/react)"
                  className="w-full bg-transparent text-white pl-12 pr-4 py-3 rounded-xl outline-none placeholder:text-zinc-600 font-mono transition-colors focus:bg-white/5"
                  disabled={loading}
                />
              </div>
              <button
                type="submit"
                disabled={loading || !repo.trim()}
                className="btn-glow sm:w-auto w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-black" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Scanning...</span>
                  </>
                ) : (
                  <>
                    <span>Analyze Repository</span>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                  </>
                )}
              </button>
            </div>
          </div>
          {error && <p className="mt-3 text-sm text-red-400 font-mono animate-fade-in text-center">{error}</p>}
        </form>

        {/* Preset Repos */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3 text-sm font-sans text-zinc-500 animate-slide-up stagger-5">
          <span>Popular Targets:</span>
          {['facebook/react', 'psf/requests', 'expressjs/express', 'octocat/Hello-World'].map(r => (
            <button
              key={r}
              type="button"
              onClick={() => setRepo(r)}
              className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 hover:border-white/30 hover:text-white transition-all hover:bg-white/10"
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Recent Scans Section */}
      {recent.length > 0 && (
        <div className="w-full mt-24 pt-10 border-t border-white/5 animate-slide-up stagger-5">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-400">
              Recent Analysis Logs
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recent.slice(0, 6).map((scan, idx) => (
              <Link
                key={scan.id}
                href={`/report/${scan.id}`}
                className="glass-panel p-5 flex flex-col gap-4 group"
              >
                <div className="flex justify-between items-start">
                  <div className="font-mono text-sm font-semibold text-white truncate group-hover:text-zinc-300 transition-colors">
                    {scan.repo}
                  </div>
                  <TierBadge scan={scan} size="sm" showTagline={false} />
                </div>
                <div className="text-xs font-mono text-zinc-500 flex items-center justify-between border-t border-white/5 pt-3">
                  <span>{scan.files ?? 1} files</span>
                  <span>{(scan.loc ?? 0).toLocaleString()} LOC</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      <footer className="w-full mt-24 py-6 text-center text-sm text-zinc-600 border-t border-white/5">
        SkillIssue &copy; {new Date().getFullYear()} &mdash; Advanced Autonomous Code Health Diagnostics.
      </footer>
    </main>
  )
}
