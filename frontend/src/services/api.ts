import type { ImpactSummary, Recommendation, Shipment, ShipmentDetail, TelemetryPoint } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try { const body = await response.json(); message = body?.detail ?? message } catch { /* non-JSON response */ }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  shipments: () => request<Shipment[]>('/api/shipments'),
  shipment: (id: string) => request<ShipmentDetail>(`/api/shipments/${encodeURIComponent(id)}`),
  telemetry: (id: string) => request<TelemetryPoint[]>(`/api/shipments/${encodeURIComponent(id)}/telemetry`),
  recommendations: () => request<Recommendation[]>('/api/recommendations'),
  approve: (id: string) => request(`/api/recommendations/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  reject: (id: string) => request(`/api/recommendations/${encodeURIComponent(id)}/reject`, { method: 'POST' }),
  quarantine: (id: string) => request(`/api/shipments/${encodeURIComponent(id)}/quarantine`, { method: 'POST' }),
  scenario: (shipment_id: string, scenario: string, duration_minutes = 10) => request('/api/sim/scenario', {
    method: 'POST', body: JSON.stringify({ shipment_id, scenario, duration_minutes }),
  }),
  impact: () => request<ImpactSummary>('/api/impact/summary'),
}

export { API_BASE }
