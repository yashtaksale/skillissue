'use client'

import { useEffect, useState } from 'react'
import { getReport, type ReportData } from '@/lib/api'
import { CATEGORIES, SEVERITY_COLORS, type Finding } from '@/lib/types'

export default function ReportPage({ params }: { params: { id: string } }) {
  const [report, setReport] = useState<ReportData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeCat, setActiveCat] = useState<string>('all')

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const data = await getReport(params.id)
        if (!cancelled) setReport(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load report')
      }
    }
    poll()
    const interval = setInterval(poll, 3000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [params.id])

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-lg text-red-500">{error}</p>
          <a href="/" className="mt-4 text-sm text-gray-500 hover:text-gray-300">← Back to home</a>
        </div>
      </main>
    )
  }
  if (!report) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400 animate-pulse-soft">Loading report…</p>
      </main>
    )
  }

  const filteredFindings = activeCat === 'all'
    ? report.findings
    : report.findings.filter(f => f.category === activeCat)

  return (
    <main className="max-w-5xl mx-auto px-4 py-12">
      {/* Header */}
      <div className="mb-8">
        <a href="/" className="text-sm text-gray-500 hover:text-gray-300">← New scan</a>
        <h1 className="mt-3 text-3xl font-bold tracking-tight">{report.repo}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {report.ref} @ <span className="font-mono">{report.commit_sha}</span>
        </p>
      </div>

      {/* Score Card */}
      <ScoreCard report={report} />

      {/* Summary */}
      <div className="mt-8 rounded-2xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-raised p-6">
        <p className="text-base text-gray-700 dark:text-gray-300">{report.summary}</p>
      </div>

      {/* Stats Grid */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Files Scanned" value={report.files_scanned.toLocaleString()} />
        <Stat label="Total LOC" value={report.loc_total.toLocaleString()} />
        <Stat label="Languages" value={report.languages.slice(0, 3).join(', ') || '—'} />
        <Stat label="Hygiene Flags" value={report.hygiene_flags.length.toString()} />
      </div>

      {/* Hygiene Flags */}
      {report.hygiene_flags.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-3">
            Hygiene Issues
          </h2>
          <div className="flex flex-wrap gap-2">
            {report.hygiene_flags.map(flag => (
              <span key={flag}
                    className="text-xs rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 px-3 py-1">
                {flag.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Findings */}
      <section className="mt-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
            Findings ({report.findings.length})
          </h2>
          <CategoryFilter
            active={activeCat}
            onChange={setActiveCat}
            findings={report.findings}
          />
        </div>
        {filteredFindings.length === 0 ? (
          <p className="text-sm text-gray-400">No findings in this category.</p>
        ) : (
          <div className="space-y-3">
            {filteredFindings
              .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity])
              .map(f => <FindingCard key={f.id} finding={f} />)}
          </div>
        )}
      </section>

      {/* Footer */}
      <div className="mt-16 pt-8 border-t border-gray-200 dark:border-surface-border text-center text-xs text-gray-500">
        Powered by SkillIssue · {report.coverage === 'full' ? 'Full scan' : 'Partial scan'}
      </div>
    </main>
  )
}

const SEVERITY_RANK: Record<string, number> = {
  critical: 0, high: 1, medium: 2, low: 3, info: 4,
}

function ScoreCard({ report }: { report: ReportData }) {
  const score = report.overall_score
  const color = report.tier_color

  return (
    <div className="rounded-2xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-raised p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        {/* Big score number */}
        <div>
          <div className="text-7xl font-bold tabular-nums" style={{ color }}>
            {score}
          </div>
          <div className="mt-2 text-xl font-semibold" style={{ color }}>
            {report.tier}
          </div>
        </div>

        {/* Gradient bar with marker */}
        <div className="flex-1 max-w-md">
          <div className="relative h-3 rounded-full overflow-hidden bg-gray-200 dark:bg-surface-raised">
            <div className="absolute inset-0 score-gradient" />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-1 h-7 bg-white rounded-full shadow-md"
              style={{ left: `${score}%`, transform: `translateX(-50%) translateY(-50%)` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-2">
            <span>0 — Raw</span>
            <span>100 — Burnt</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-raised p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
      <div className="mt-1 text-lg font-semibold truncate">{value}</div>
    </div>
  )
}

function CategoryFilter({
  active, onChange, findings,
}: { active: string; onChange: (k: string) => void; findings: Finding[] }) {
  const counts: Record<string, number> = {}
  for (const f of findings) counts[f.category] = (counts[f.category] ?? 0) + 1

  return (
    <div className="flex flex-wrap gap-1">
      <button
        onClick={() => onChange('all')}
        className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
          active === 'all'
            ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
            : 'bg-gray-100 dark:bg-surface-raised hover:bg-gray-200'
        }`}
      >
        All ({findings.length})
      </button>
      {CATEGORIES.map(c => {
        const count = counts[c.key] ?? 0
        if (count === 0) return null
        return (
          <button
            key={c.key}
            onClick={() => onChange(c.key)}
            className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
              active === c.key
                ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
                : 'bg-gray-100 dark:bg-surface-raised hover:bg-gray-200'
            }`}
          >
            {c.icon} {c.label} ({count})
          </button>
        )
      })}
    </div>
  )
}

function FindingCard({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false)
  const sevColor = SEVERITY_COLORS[finding.severity] ?? '#6b7280'

  return (
    <div className="rounded-xl border border-gray-200 dark:border-surface-border bg-white dark:bg-surface-raised overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full p-4 text-left flex items-start gap-3 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
      >
        <span
          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase mt-0.5"
          style={{ backgroundColor: `${sevColor}22`, color: sevColor }}
        >
          {finding.severity}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-gray-500">{finding.rule_id}</span>
            <span className="text-xs text-gray-400">·</span>
            <span className="text-xs text-gray-500">{finding.priority}</span>
            <span className="text-xs text-gray-400">·</span>
            <span className="text-xs text-gray-500">{Math.round(finding.confidence * 100)}% conf</span>
          </div>
          <div className="mt-1 font-medium">{finding.message}</div>
          <div className="mt-0.5 text-xs text-gray-500 font-mono truncate">
            {finding.file}:{finding.line}
          </div>
        </div>
        <span className="text-gray-400 mt-1">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="border-t border-gray-200 dark:border-surface-border p-4 space-y-3">
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Why this matters</div>
            <p className="text-sm">{finding.explanation}</p>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Suggested fix</div>
            <p className="text-sm">{finding.fix}</p>
          </div>
          {finding.snippet && (
            <div>
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Code</div>
              <pre className="text-xs bg-gray-50 dark:bg-surface-dark rounded-md p-3 overflow-x-auto font-mono">
                {finding.snippet}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
