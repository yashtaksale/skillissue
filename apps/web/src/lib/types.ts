export type TierName = 'Raw' | 'Lightly Toasted' | 'Medium Well' | 'Cooked' | 'Burnt to a Crisp'

export interface Tier {
  name: TierName
  emoji: string
  color: string
  min: number
  max: number
}

export const TIERS: Tier[] = [
  { name: 'Raw',              emoji: '❄️',  color: '#2B6CC4', min: 0,  max: 14 },
  { name: 'Lightly Toasted',  emoji: '☀️',  color: '#3D8B40', min: 15, max: 34 },
  { name: 'Medium Well',      emoji: '🌡️',  color: '#C9922B', min: 35, max: 59 },
  { name: 'Cooked',           emoji: '🔥',  color: '#CF3626', min: 60, max: 79 },
  { name: 'Burnt to a Crisp', emoji: '💀',  color: '#4A2A22', min: 80, max: 100 },
]

export interface Finding {
  rule_id: string
  category: string
  severity: string
  confidence: number
  message: string
  explanation: string
  fix: string
  id: string
  priority: string
  file: string
  line: number
  line_end: number
  snippet: string
}

export interface ScanRecord {
  id: string
  repo: string
  status: string
  progress: number
  score: number
  tier: string
  files: number
  loc: number
  languages: string[]
  coverage: string
  hygiene_flags: string[]
  error: string | null
  created_at: number
}

export interface ReportData {
  id: string
  repo: string
  ref: string
  commit_sha: string
  overall_score: number
  tier: string
  tier_color: string
  summary: string
  coverage: string
  files_scanned: number
  loc_total: number
  languages: string[]
  hygiene_flags: string[]
  findings: Finding[]
}

export const CATEGORIES = [
  { key: 'security',       label: 'Security',    icon: '🛡️', weight: 0.35 },
  { key: 'bugs',           label: 'Bugs',        icon: '🐛', weight: 0.25 },
  { key: 'maintainability',label: 'Maintain.',   icon: '🔧', weight: 0.15 },
  { key: 'performance',    label: 'Performance', icon: '⚡', weight: 0.10 },
  { key: 'hygiene',        label: 'Hygiene',     icon: '🧹', weight: 0.15 },
]

export const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high:     '#ef4444',
  medium:   '#f59e0b',
  low:      '#3b82f6',
  info:     '#6b7280',
}
