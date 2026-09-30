'use client'

import { getTierInfo, type ScanRecord } from '@/lib/types'

interface Props {
  scan?: ScanRecord
  tierName?: string
  score?: number
  size?: 'sm' | 'md' | 'lg'
  showTagline?: boolean
}

export function TierBadge({ scan, tierName, score, size = 'md', showTagline = true }: Props) {
  const name = scan ? scan.tier : (tierName ?? 'Raw')
  const s = scan ? scan.score : (score ?? 0)
  const tier = getTierInfo(name, s)

  const sizeClasses = {
    sm: 'px-2.5 py-0.5 text-xs gap-1.5',
    md: 'px-3 py-1 text-xs sm:text-sm gap-2',
    lg: 'px-4 py-1.5 text-sm font-semibold gap-2',
  }[size]

  return (
    <span
      className={`inline-flex items-center rounded-full font-mono font-medium border bg-white/5 text-white border-white/10 transition-all duration-300 hover:scale-105 hover:border-white/30 hover:bg-white/10 active:scale-95 cursor-default shadow-[0_4px_12px_rgba(0,0,0,0.1)] ${sizeClasses}`}
    >
      <span className="animate-flame">{tier.emoji}</span>
      <span className="tracking-tight uppercase">{tier.name}</span>
      {showTagline && <span className="opacity-60 font-normal text-[0.9em] lowercase tracking-wide ml-1">({tier.tagline})</span>}
    </span>
  )
}

