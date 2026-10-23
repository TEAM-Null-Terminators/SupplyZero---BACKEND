import { create } from 'zustand'
import type { Recommendation, Shipment, TelemetryPoint } from '../types'
import type { Health } from '../types'

interface FleetState {
  shipments: Shipment[]
  recommendations: Recommendation[]
  telemetry: Record<string, TelemetryPoint[]>
  wsStatus: 'connecting' | 'live' | 'offline'
  offlineMode: boolean
  setShipments: (items: Shipment[]) => void
  setRecommendations: (items: Recommendation[]) => void
  setTelemetry: (shipmentId: string, items: TelemetryPoint[]) => void
  setConnection: (status: FleetState['wsStatus'], offline: boolean) => void
  applyEvent: (event: Record<string, unknown>) => void
  tickDemo: () => void
  applyDemoScenario: (shipmentId: string, scenario: string) => void
}

const demoShipments: Shipment[] = [
  { id: 'SZ-1042', product: 'Cold vaccine', category: 'PHARMA', status: 'ACTIVE', quantity_kg: 420, current_lat: 26.4499, current_lon: 80.3319, state: { health: 'GREEN', rsl_h: 318, rsl_pct: 74, mkt_c: 5.2, tts_expected_h: 312, life_consumed_h: 185 } },
  { id: 'SZ-1058', product: 'Fresh berries', category: 'PRODUCE', status: 'ACTIVE', quantity_kg: 860, current_lat: 26.62, current_lon: 80.49, state: { health: 'AMBER', rsl_h: 36, rsl_pct: 29, mkt_c: 7.1, tts_expected_h: 32, life_consumed_h: 84 } },
  { id: 'SZ-1081', product: 'Insulin', category: 'PHARMA', status: 'ACTIVE', quantity_kg: 240, current_lat: 26.73, current_lon: 80.66, state: { health: 'RED', rsl_h: 0, rsl_pct: 0, mkt_c: 10.4, tts_expected_h: 0, life_consumed_h: 1000, hard_stop: true } },
  { id: 'SZ-1093', product: 'Leafy greens', category: 'PRODUCE', status: 'ACTIVE', quantity_kg: 620, current_lat: 26.54, current_lon: 80.29, state: { health: 'GREEN', rsl_h: 112, rsl_pct: 68, mkt_c: 3.6, tts_expected_h: 108, life_consumed_h: 56 } },
]

const demoRecommendations: Recommendation[] = [
  { id: 'demo-1', shipment_id: 'SZ-1058', ts: new Date().toISOString(), action: 'REROUTE', status: 'PENDING', target_hub_name: 'Kanpur Hub', saving: 18600, co2e_avoided: 124, rationale: 'Rerouting to Kanpur Hub saves 860 kg of berries before their remaining life falls below the sellable threshold.' },
  { id: 'demo-2', shipment_id: 'SZ-1081', ts: new Date().toISOString(), action: 'QUARANTINE', status: 'PENDING', saving: -12000, rationale: 'A freeze excursion was detected in this insulin load. Quarantine the shipment for QA review.' },
]

const demoTelemetry = Object.fromEntries(demoShipments.map((shipment, index) => [shipment.id,
  Array.from({ length: 24 }, (_, point) => ({
    ts: new Date(Date.now() - (23 - point) * 5 * 60_000).toISOString(),
    temp_c: Number((4.4 + Math.sin(point / 3 + index) * 0.55 + (index === 1 && point > 16 ? (point - 16) * 0.55 : 0)).toFixed(1)),
    humidity: 65 + point % 8,
  })),
])) as Record<string, TelemetryPoint[]>

export const useFleetStore = create<FleetState>((set) => ({
  shipments: demoShipments,
  recommendations: demoRecommendations,
  telemetry: demoTelemetry,
  wsStatus: 'connecting',
  offlineMode: true,
  setShipments: (items) => set({ shipments: items }),
  setRecommendations: (items) => set({ recommendations: items }),
  setTelemetry: (id, items) => set((state) => ({ telemetry: { ...state.telemetry, [id]: items.slice(-200) } })),
  setConnection: (wsStatus, offlineMode) => set({ wsStatus, offlineMode }),
  applyEvent: (event) => set((state) => {
    const id = String(event.shipment_id ?? '')
    if (!id) return state
    const shipments = state.shipments.map((shipment) => shipment.id === id ? {
      ...shipment,
      current_lat: typeof event.lat === 'number' ? event.lat : shipment.current_lat,
      current_lon: typeof event.lon === 'number' ? event.lon : shipment.current_lon,
      current_temp: typeof event.temp_c === 'number' ? event.temp_c : shipment.current_temp,
      state: { ...shipment.state, ...('health' in event ? { health: event.health as Health } : {}),
        ...('rsl_h' in event ? { rsl_h: Number(event.rsl_h) } : {}),
        ...('rsl_pct' in event ? { rsl_pct: Number(event.rsl_pct) } : {}),
        ...('tts_expected_h' in event ? { tts_expected_h: Number(event.tts_expected_h) } : {}),
      },
    } : shipment)
    const eventType = String(event.type ?? '')
    if (eventType === 'recommendation' && event.recommendation && typeof event.recommendation === 'object') {
      return { shipments, recommendations: [event.recommendation as Recommendation, ...state.recommendations] }
    }
    return { shipments }
  }),
  tickDemo: () => set((state) => {
    const telemetry = { ...state.telemetry }
    const shipments = state.shipments.map((shipment, index) => {
      const prior = telemetry[shipment.id] ?? []
      const last = prior.at(-1)?.temp_c ?? 4.5
      const bump = shipment.state?.health === 'RED' ? 0.2 : shipment.state?.health === 'AMBER' ? 0.35 : 0.08
      const temp = Number((last + (Math.random() - 0.58) * bump).toFixed(2))
      telemetry[shipment.id] = [...prior, { ts: new Date().toISOString(), temp_c: temp }].slice(-200)
      const rslPct = Math.max(0, Math.min(100, (shipment.state?.rsl_pct ?? 75) - (index === 1 ? 0.04 : 0.008)))
      const health: Health = shipment.state?.hard_stop ? 'RED' : rslPct < 30 ? 'RED' : rslPct < 60 ? 'AMBER' : 'GREEN'
      return { ...shipment, state: { ...shipment.state, health, rsl_pct: rslPct, rsl_h: Math.max(0, (shipment.state?.rsl_h ?? 300) - 0.02) } }
    })
    return { telemetry, shipments }
  }),
  applyDemoScenario: (shipmentId, scenario) => set((state) => {
    const shipment = state.shipments.find((item) => item.id === shipmentId)
    if (!shipment || scenario === 'sensor_dropout') return state
    const delta: Record<string, number> = { compressor_failure: 9, freeze: -11, door_open: 13, heatwave: 8, normal: 0 }
    const temp = Number(((state.telemetry[shipmentId]?.at(-1)?.temp_c ?? 5) + (delta[scenario] ?? 0)).toFixed(1))
    const atRisk = scenario === 'freeze' || scenario === 'compressor_failure' || scenario === 'heatwave' || scenario === 'door_open'
    const health: Health = scenario === 'freeze' ? 'RED' : scenario === 'normal' ? 'GREEN' : 'AMBER'
    const telemetry = { ...state.telemetry, [shipmentId]: [...(state.telemetry[shipmentId] ?? []), { ts: new Date().toISOString(), temp_c: temp, door_open: scenario === 'door_open' }].slice(-200) }
    const shipments = state.shipments.map((item) => item.id === shipmentId ? { ...item,
      state: { ...item.state, health, hard_stop: scenario === 'freeze', rsl_pct: Math.max(0, (item.state?.rsl_pct ?? 70) - (atRisk ? 12 : 0)), rsl_h: Math.max(0, (item.state?.rsl_h ?? 200) - (atRisk ? 12 : 0)) },
    } : item)
    const recommendations = scenario === 'freeze' ? [{ id: `demo-${Date.now()}`, shipment_id: shipmentId, ts: new Date().toISOString(), action: 'QUARANTINE' as const, status: 'PENDING', rationale: `A freeze excursion was injected for ${shipmentId}. Quarantine the shipment for QA review.` }, ...state.recommendations] : state.recommendations
    return { telemetry, shipments, recommendations }
  }),
}))
