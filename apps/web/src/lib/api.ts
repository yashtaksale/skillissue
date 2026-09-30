import type { ReportData, ScanRecord } from './types'

export type { ReportData, ScanRecord }

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function fetchJson(url: string, options: RequestInit = {}): Promise<Response> {
  const res = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string> || {}) } })
  return res
}

export async function startScan(repo: string): Promise<ScanRecord> {
  const res = await fetchJson(`${API_URL}/api/scans`, {
    method: 'POST',
    body: JSON.stringify({ repo }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof detail.detail === 'string' ? detail.detail : JSON.stringify(detail.detail ?? detail)
    throw new Error(msg)
  }
  return res.json()
}

export async function getScan(id: string): Promise<ScanRecord> {
  const res = await fetchJson(`${API_URL}/api/scans/${id}`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch scan: ${res.status}`)
  return res.json()
}

export async function getReport(id: string): Promise<ReportData> {
  const res = await fetchJson(`${API_URL}/api/scans/${id}/report`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch report: ${res.status}`)
  return res.json()
}

export async function listScans(): Promise<{ scans: ScanRecord[] }> {
  const res = await fetchJson(`${API_URL}/api/scans`, { cache: 'no-store' })
  if (!res.ok) return { scans: [] }
  return res.json()
}

export function scanStreamUrl(id: string): string {
  return `${API_URL}/api/scans/${id}/stream`
}
