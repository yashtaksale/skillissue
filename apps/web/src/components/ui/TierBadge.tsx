'use client'

import { TIERS, type ScanRecord } from '@/lib/types'

interface Props {
  scan: ScanRecord
}

export function TierBadge({ scan }: Props) {
  const tier = TIERS.find(t => t.name === scan.tier) ?? TIERS[0]

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold"
      style={{ backgroundColor: `${tier.color}22`, color: tier.color }}
    >
      <span>{tier.emoji}</span>
      <span>{scan.tier}</span>
    </span>
  )
}
