import type { ReportData, ScanRecord } from './types'

export type { ReportData, ScanRecord }

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function startScan(repo: string): Promise<ScanRecord> {
  const res = await fetch(`${API_URL}/api/scans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? `Scan request failed: ${res.status}`)
  }
  return res.json()
}

export async function getScan(id: string): Promise<ScanRecord> {
  const res = await fetch(`${API_URL}/api/scans/${id}`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch scan: ${res.status}`)
  return res.json()
}

export async function getReport(id: string): Promise<ReportData> {
  const res = await fetch(`${API_URL}/api/scans/${id}/report`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch report: ${res.status}`)
  return res.json()
}

export async function listScans(): Promise<{ scans: ScanRecord[] }> {
  const res = await fetch(`${API_URL}/api/scans`, { cache: 'no-store' })
  if (!res.ok) return { scans: [] }
  return res.json()
}

export function scanStreamUrl(id: string): string {
  return `${API_URL}/api/scans/${id}/stream`
}
