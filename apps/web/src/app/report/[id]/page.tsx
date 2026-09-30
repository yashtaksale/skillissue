'use client'

import { useEffect, useState } from 'react'
import { getReport, type ReportData } from '@/lib/api'
import { CATEGORIES, SEVERITY_COLORS, getTierInfo, type Finding } from '@/lib/types'
import { TierBadge } from '@/components/ui/TierBadge'

export default function ReportPage({ params }: { params: { id: string } }) {
  const [report, setReport] = useState<ReportData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeCat, setActiveCat] = useState<string>('all')
  const [copied, setCopied] = useState(false)
  const [displayScore, setDisplayScore] = useState(0)

  useEffect(() => {
    let cancelled = false
    let interval: ReturnType<typeof setInterval> | null = null

    const poll = async () => {
      try {
        const data = await getReport(params.id)
        if (!cancelled) {
          setReport(data)
          // Stop polling once report loads successfully
          if (interval) {
            clearInterval(interval)
            interval = null
          }
        }
      } catch (err) {
        if (!cancelled) {
          // Only keep polling if it's a 409 (scan not yet complete)
          const msg = err instanceof Error ? err.message : 'Failed to load report'
          if (!msg.includes('409')) {
            setError(msg)
            if (interval) {
              clearInterval(interval)
              interval = null
            }
          }
        }
      }
    }
    poll()
    interval = setInterval(poll, 3000)
    return () => { cancelled = true; if (interval) clearInterval(interval) }
  }, [params.id])

  // Animated Score Counter Effect
  useEffect(() => {
    if (!report) return
    const target = report.overall_score
    const duration = 1200
    const steps = 30
    const increment = target / steps
    let current = 0
    const timer = setInterval(() => {
      current += increment
      if (current >= target) {
        setDisplayScore(target)
        clearInterval(timer)
      } else {
        setDisplayScore(Math.round(current))
      }
    }, duration / steps)
    return () => clearInterval(timer)
  }, [report?.overall_score])

  function handleShare() {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4 font-sans bg-grid-pattern">
        <div className="glass-panel p-6 text-center max-w-sm animate-pop-in">
          <p className="text-sm text-zinc-400 mb-4">{error}</p>
          <a href="/" className="text-xs text-white underline hover:text-zinc-300">← Back to home</a>
        </div>
      </main>
    )
  }

  if (!report) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4 font-sans bg-grid-pattern">
        <div className="flex flex-col items-center gap-6">
          {/* Minimal loader */}
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 rounded-full border-t-2 border-white animate-spin" />
          </div>
          <p className="text-xs text-zinc-400 animate-pulse font-mono tracking-widest uppercase">Calculating Heat...</p>
        </div>
      </main>
    )
  }

  const tier = getTierInfo(report.tier, report.overall_score)
  const filteredFindings = activeCat === 'all'
    ? report.findings
    : report.findings.filter(f => f.category === activeCat)

  // Radial Gauge Math
  const gaugeRadius = 38
  const gaugeCircumference = 2 * Math.PI * gaugeRadius
  const strokeDashoffset = gaugeCircumference - (displayScore / 100) * gaugeCircumference

  return (
    <main className="min-h-screen px-4 py-8 max-w-4xl mx-auto space-y-8 font-sans relative overflow-hidden animate-fade-in">
      
      {/* Background Subtle Ambient Glow */}
      <div className="absolute top-0 right-0 w-full h-96 bg-gradient-to-b from-neon-purple/5 to-transparent pointer-events-none" />

      {/* Top Navbar Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/5 font-mono text-xs relative z-10">
        <a href="/" className="text-zinc-500 hover:text-white transition-all flex items-center gap-2 group">
          <span className="group-hover:-translate-x-1 transition-transform">←</span>
          <span>New Scan</span>
        </a>
        <button
          onClick={handleShare}
          className="px-4 py-1.5 rounded-full border border-white/10 bg-white/5 text-zinc-300 hover:border-white/30 hover:text-white transition-all active:scale-95 flex items-center gap-2 cursor-pointer"
        >
          <span>{copied ? '✓' : '🔗'}</span>
          <span>{copied ? 'Link Copied!' : 'Share Report'}</span>
        </button>
      </div>

      {/* Repo Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono relative z-10 animate-slide-up">
        <div>
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white flex items-center gap-3">
            <span className="text-zinc-500 text-2xl">⚡</span>
            <span>{report.repo}</span>
          </h1>
          <p className="text-xs text-zinc-400 mt-2 flex items-center gap-2 font-mono">
            <span>Ref: <strong className="text-white">{report.ref || 'main'}</strong></span>
            <span className="text-white/20">•</span>
            <span>Commit: <strong className="text-white">{(report.commit_sha || 'head').slice(0, 7)}</strong></span>
          </p>
        </div>

        <TierBadge tierName={report.tier} score={report.overall_score} size="lg" />
      </div>

      {/* Animated Glass Score Card with SVG Radial Ring Gauge */}
      <div className="glass-panel p-8 space-y-6 relative z-10 animate-slide-up stagger-1">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-8">
          
          {/* Left Score Gauge Block */}
          <div className="flex items-center gap-6">
            {/* Minimal Animated SVG Ring Gauge */}
            <div className="relative w-28 h-28 flex items-center justify-center shrink-0">
              <svg className="relative w-full h-full transform -rotate-90" viewBox="0 0 96 96">
                <circle
                  cx="48"
                  cy="48"
                  r={gaugeRadius}
                  className="stroke-white/10"
                  strokeWidth="6"
                  fill="transparent"
                />
                <circle
                  cx="48"
                  cy="48"
                  r={gaugeRadius}
                  className="stroke-white transition-all duration-1000 ease-out"
                  strokeWidth="6"
                  strokeDasharray={gaugeCircumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  fill="transparent"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center text-4xl font-semibold text-white tabular-nums">
                {displayScore}
              </div>
            </div>

            <div>
              <div className="text-lg sm:text-xl font-semibold text-white flex items-center gap-2 uppercase tracking-wide">
                <span>{tier.emoji}</span>
                <span>{tier.name}</span>
              </div>
              <div className="text-xs font-mono text-zinc-400 mt-1">
                &ldquo;{tier.tagline}&rdquo;
              </div>
            </div>
          </div>

          {/* Minimal Heat Bar */}
          <div className="flex-1 max-w-xs w-full space-y-2 font-mono">
            <div className="flex justify-between text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
              <span>0 (RAW)</span>
              <span className="text-white">{displayScore}% COOKED</span>
              <span>100 (BURNT)</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden relative">
              <div
                className="h-full bg-white transition-all duration-1000 ease-out relative"
                style={{ width: `${displayScore}%` }}
              >
              </div>
            </div>
          </div>
        </div>

        {report.summary && (
          <p className="text-sm text-zinc-300 pt-4 border-t border-white/5 leading-relaxed font-sans opacity-90">
            {report.summary}
          </p>
        )}
      </div>

      {/* Glass Animated Stat Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono relative z-10 animate-slide-up stagger-2">
        <Stat label="Files Scanned" value={report.files_scanned?.toLocaleString() ?? '1'} icon="📁" />
        <Stat label="Total LOC" value={report.loc_total?.toLocaleString() ?? '0'} icon="📊" />
        <Stat label="Coverage" value={report.coverage === 'full' ? 'Full' : 'Sampled'} icon="🎯" />
        <Stat label="Hygiene Penalties" value={`${report.hygiene_flags?.length ?? 0}`} icon="🧹" />
      </div>

      {/* Hygiene Flags */}
      {report.hygiene_flags && report.hygiene_flags.length > 0 && (
        <div className="glass-panel p-5 space-y-3 font-mono relative z-10 animate-slide-up stagger-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
            <span>⚠️</span> Hygiene Issues Detected
          </h2>
          <div className="flex flex-wrap gap-2 pt-1">
            {report.hygiene_flags.map((flag, idx) => (
              <span
                key={flag}
                className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white text-[11px] font-semibold transition-all hover:bg-white/10 cursor-default"
                style={{ animationDelay: `${idx * 40}ms` }}
              >
                {flag.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Findings Section */}
      <div className="space-y-6 pt-4 relative z-10 animate-slide-up stagger-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-white flex items-center gap-2">
            <span className="text-zinc-500">❯</span> Findings ({report.findings.length})
          </h2>

          {/* Category Filter Tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setActiveCat('all')}
              className={`px-4 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider transition-all cursor-pointer ${
                activeCat === 'all'
                  ? 'bg-white text-black shadow-[0_0_15px_rgba(255,255,255,0.3)]'
                  : 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              All ({report.findings.length})
            </button>
            {CATEGORIES.map(c => {
              const count = report.findings.filter(f => f.category === c.key).length
              if (count === 0) return null
              return (
                <button
                  key={c.key}
                  onClick={() => setActiveCat(c.key)}
                  className={`px-4 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider transition-all cursor-pointer ${
                    activeCat === c.key
                      ? 'bg-white text-black shadow-[0_0_15px_rgba(255,255,255,0.3)]'
                      : 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  {c.label} ({count})
                </button>
              )
            })}
          </div>
        </div>

        {/* Findings List */}
        {filteredFindings.length === 0 ? (
          <div className="glass-panel py-10 text-center flex flex-col items-center justify-center">
            <span className="text-3xl mb-3">✨</span>
            <p className="text-sm text-zinc-400 font-sans">No findings in this category. Clean code!</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredFindings
              .sort((a, b) => (SEVERITY_RANK[a.severity] ?? 99) - (SEVERITY_RANK[b.severity] ?? 99))
              .map((finding, idx) => (
                <FindingCard key={finding.id} finding={finding} />
              ))}
          </div>
        )}
      </div>

      <footer className="pt-8 border-t border-white/5 text-center text-[11px] font-mono text-zinc-600 relative z-10">
        SkillIssue Engine • Scan ID: <span className="text-zinc-500">{params.id}</span>
      </footer>
    </main>
  )
}

const SEVERITY_RANK: Record<string, number> = {
  critical: 0, high: 1, medium: 2, low: 3, info: 4,
}

function Stat({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="glass-panel p-4 transition-all hover:-translate-y-1">
      <div className="text-[10px] uppercase tracking-wider font-bold text-zinc-500 flex items-center gap-1.5">
        <span>{icon}</span>
        <span>{label}</span>
      </div>
      <div className="text-lg sm:text-xl font-semibold text-white mt-1 truncate">{value}</div>
    </div>
  )
}

function FindingCard({ finding }: { finding: Finding }) {
  const sevStyle = SEVERITY_COLORS[finding.severity.toLowerCase()] ?? SEVERITY_COLORS.info

  const locationText = finding.file
    ? (finding.line > 0
        ? (finding.line_end && finding.line_end > finding.line
            ? `${finding.file}:${finding.line}-${finding.line_end}`
            : `${finding.file}:${finding.line}`)
        : finding.file)
    : 'Repository Level'

  const [copiedLoc, setCopiedLoc] = useState(false)
  const [expanded, setExpanded] = useState(true)

  function handleCopyLoc(e: React.MouseEvent) {
    e.stopPropagation()
    navigator.clipboard.writeText(locationText)
    setCopiedLoc(true)
    setTimeout(() => setCopiedLoc(false), 2000)
  }

  return (
    <div className="glass-panel p-5 sm:p-6 space-y-4">
      {/* Top Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/5">
        <div className="flex items-center gap-3">
          <span
            className="px-3 py-1 rounded-full text-[10px] font-mono font-bold uppercase tracking-widest border"
            style={{
              backgroundColor: `${sevStyle.bg}20`,
              color: sevStyle.fg,
              borderColor: `${sevStyle.bg}40`,
              boxShadow: `0 0 10px ${sevStyle.bg}20`,
            }}
          >
            {sevStyle.label || finding.severity}
          </span>
          <span className="text-xs font-mono text-zinc-400 bg-white/5 px-2 py-0.5 rounded">
            {finding.rule_id}
          </span>
        </div>

        {/* Copy Location Button */}
        <button
          onClick={handleCopyLoc}
          title="Copy file path"
          className="text-[11px] font-mono text-zinc-400 hover:text-white px-3 py-1.5 rounded-full bg-white/5 border border-white/10 hover:border-white/30 flex items-center gap-2 cursor-pointer transition-all active:scale-95"
        >
          <span>📍</span>
          <span className="truncate max-w-[150px] sm:max-w-[300px]">{locationText}</span>
          {copiedLoc && <span className="text-white font-bold">✓</span>}
        </button>
      </div>

      {/* Finding Title & Explanation */}
      <div>
        <h4 className="text-base sm:text-lg font-bold text-white leading-snug font-sans">
          {finding.message}
        </h4>
        {finding.explanation && (
          <p className="mt-2 text-sm text-zinc-400 leading-relaxed font-sans opacity-90">
            {finding.explanation}
          </p>
        )}
      </div>

      {/* Expandable Code Snippet Container */}
      {finding.snippet && (
        <div className="rounded-xl border border-white/10 font-mono text-xs overflow-hidden bg-black/40">
          <div
            onClick={() => setExpanded(!expanded)}
            className="px-4 py-2.5 text-[11px] text-zinc-400 border-b border-white/5 flex justify-between items-center cursor-pointer hover:bg-white/5 transition-colors select-none"
          >
            <span className="font-semibold flex items-center gap-2 uppercase tracking-wider">
              <span className={`transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>
              <span>Code Snippet</span>
            </span>
            <span className="text-zinc-500 font-semibold">{finding.file}:{finding.line}</span>
          </div>
          {expanded && (
            <div className="p-4 overflow-x-auto text-zinc-300">
              <pre className="whitespace-pre-wrap leading-loose">{finding.snippet}</pre>
            </div>
          )}
        </div>
      )}

      {/* Fix Recommendation */}
      {finding.fix && (
        <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-zinc-200 text-sm flex items-start gap-3">
          <span className="text-lg">💡</span>
          <div>
            <strong className="block text-[11px] text-zinc-300 uppercase tracking-wider font-bold mb-1">Recommendation</strong>
            <span className="text-zinc-300 leading-relaxed font-sans">{finding.fix}</span>
          </div>
        </div>
      )}
    </div>
  )
}

