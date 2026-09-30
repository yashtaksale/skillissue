export type TierName = 'Raw' | 'Lightly Toasted' | 'Medium Well' | 'Cooked' | 'Burnt to a Crisp'

export interface Tier {
  name: TierName
  tagline: string
  emoji: string
  color: string
  bgGlow: string
  min: number
  max: number
}

export const TIERS: Tier[] = [
  { name: 'Raw',              tagline: "Ain't Ready",    emoji: '🥶', color: '#FFFFFF', bgGlow: 'rgba(255, 255, 255, 0.1)', min: 0,  max: 14 },
  { name: 'Lightly Toasted',  tagline: "Lil' Toasty",    emoji: '😏', color: '#E4E4E7', bgGlow: 'rgba(228, 228, 231, 0.1)', min: 15, max: 34 },
  { name: 'Medium Well',      tagline: 'Just Right',     emoji: '😎', color: '#A1A1AA', bgGlow: 'rgba(161, 161, 170, 0.1)', min: 35, max: 59 },
  { name: 'Cooked',           tagline: 'Cooked AF',      emoji: '🔥', color: '#71717A', bgGlow: 'rgba(113, 113, 122, 0.1)', min: 60, max: 79 },
  { name: 'Burnt to a Crisp', tagline: "It's Overcooked",emoji: '💀', color: '#FFFFFF', bgGlow: 'rgba(255, 255, 255, 0.15)', min: 80, max: 100 },
]

export function getTierInfo(tierName: string, score: number = 0): Tier {
  if (!tierName) return TIERS[0]
  const normalized = tierName.toLowerCase()
  if (normalized.includes('raw') || normalized.includes("ready")) return TIERS[0]
  if (normalized.includes('light') || normalized.includes('toasty') || normalized.includes('toasted')) return TIERS[1]
  if (normalized.includes('medium') || normalized.includes('right')) return TIERS[2]
  if (normalized.includes('burnt') || normalized.includes('overcooked') || normalized.includes('crisp')) return TIERS[4]
  if (normalized.includes('cooked') || normalized.includes('af')) return TIERS[3]
  
  if (score < 15) return TIERS[0]
  if (score < 35) return TIERS[1]
  if (score < 60) return TIERS[2]
  if (score < 80) return TIERS[3]
  return TIERS[4]
}

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
  { key: 'security',       label: 'Security',    icon: '🛡️', weight: 0.35, color: '#FFFFFF' },
  { key: 'bugs',           label: 'Bugs',        icon: '🐛', weight: 0.25, color: '#E4E4E7' },
  { key: 'maintainability',label: 'Maintainability', icon: '🔧', weight: 0.15, color: '#A1A1AA' },
  { key: 'performance',    label: 'Performance', icon: '⚡', weight: 0.10, color: '#71717A' },
  { key: 'hygiene',        label: 'Hygiene',     icon: '🧹', weight: 0.15, color: '#52525B' },
]

export const SEVERITY_COLORS: Record<string, { fg: string; bg: string; border: string; label: string }> = {
  critical: { fg: '#FFFFFF', bg: '#27272A', border: '#52525B', label: '💀 CRITICAL • CHOPPED' },
  high:     { fg: '#F4F4F5', bg: '#18181B', border: '#3F3F46', label: '📉 HIGH • 0 RIZZ' },
  medium:   { fg: '#E4E4E7', bg: '#09090B', border: '#27272A', label: '⚠️ MEDIUM • MID' },
  low:      { fg: '#A1A1AA', bg: '#0A0A0A', border: '#27272A', label: '🤡 LOW • SUS' },
  info:     { fg: '#71717A', bg: '#09090B', border: '#18181B', label: '💡 INFO • SIDE QUEST' },
}
