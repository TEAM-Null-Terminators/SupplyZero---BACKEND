export type Health = 'GREEN' | 'AMBER' | 'RED'
export type Action = 'CONTINUE' | 'REROUTE' | 'CLEARANCE' | 'QUARANTINE'

export interface ShipmentState {
  ts?: string
  health?: Health
  rsl_h?: number
  rsl_pct?: number
  mkt_c?: number | null
  tts_expected_h?: number
  tts_optimistic_h?: number
  tts_pessimistic_h?: number
  life_consumed_h?: number
  hard_stop?: boolean
}

export interface Shipment {
  id: string
  product?: string
  product_id?: string
  status?: string
  current_lat?: number | null
  current_lon?: number | null
  quantity_kg?: number
  state?: ShipmentState | null
  telemetry?: { temp_c?: number; ts?: string }[]
  current_temp?: number
  category?: string
}

export interface Recommendation {
  id: string
  shipment_id: string
  ts: string
  action: Action
  target_hub_id?: string | null
  rsl_at_arrival?: number | null
  score?: number | null
  net_value?: number
  baseline_value?: number
  saving?: number
  co2e_avoided?: number
  rationale?: string
  status: string
  scoring_breakdown?: Record<string, unknown>
  target_hub_name?: string
}

export interface TelemetryPoint {
  ts: string
  temp_c: number
  humidity?: number
  door_open?: boolean
}

export interface ShipmentDetail {
  shipment: Shipment & { value?: number; planned_eta?: string }
  state?: ShipmentState | null
  excursions?: { id: string; start_ts: string; end_ts: string; peak_temp: number; duration_min: number; rule_breached?: string }[]
  nominal_expiry_ts?: string | null
}

export interface ImpactSummary { value_saved: number; co2e_avoided_kg: number; kg_diverted: number; baseline_value?: number; supplyzero_value?: number; currency?: string }
