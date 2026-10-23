import { useEffect } from 'react'
import { AlertTriangle, ArrowRight, Clock3, Thermometer, X } from 'lucide-react'
import type { ShipmentDetail, TelemetryPoint } from '../types'
import { TelemetryChart } from './TelemetryChart'
import { ErrorBoundary } from './ErrorBoundary'
import { RslRing } from './RslRing'
import { StatusBadge } from './StatusBadge'

export function DetailModal({ detail, telemetry, loading, onClose, onQuarantine }: { detail?: ShipmentDetail; telemetry: TelemetryPoint[]; loading: boolean; onClose: () => void; onQuarantine: () => void }) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])
  const shipment = detail?.shipment
  const state = detail?.state
  const health = state?.health ?? 'GREEN'
  const last = telemetry.at(-1)?.temp_c
  const firstTime = telemetry[0]?.ts
  const lastTime = telemetry.at(-1)?.ts
  const dynamicExpiry = state?.ts && state.tts_expected_h != null
    ? new Date(new Date(state.ts).getTime() + state.tts_expected_h * 3_600_000).toLocaleDateString()
    : null
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}><section className="detail-modal modal-panel" role="dialog" aria-modal="true" aria-labelledby="detail-title">
    <header className="modal-header"><div><span className="eyebrow">SHIPMENT INTELLIGENCE</span><h2 id="detail-title">{shipment?.id ?? 'Shipment details'} <StatusBadge health={health} /></h2><p>{shipment?.product ?? 'Cold-chain shipment'} · Batch-level kinetic history</p></div><div className="modal-header-actions"><button className="quarantine-button" onClick={onQuarantine}>Quarantine for QA</button><button className="icon-button" onClick={onClose} aria-label="Close details"><X size={19} /></button></div></header>
    {loading && <div className="loading-strip"><span className="spinner" /> Syncing recent telemetry…</div>}
    <div className="detail-overview"><div className="detail-rsl"><RslRing size={76} value={state?.rsl_pct ?? 0} health={health} /><div><span>Remaining shelf life</span><strong>{state?.rsl_h == null ? '—' : `${state.rsl_h.toFixed(1)} h`}</strong><small>of product’s modeled usable life</small></div></div><div className="detail-stat"><Thermometer size={16} /><span>Latest temperature</span><strong>{last == null ? '—' : `${last.toFixed(1)}°C`}</strong></div><div className="detail-stat"><Clock3 size={16} /><span>Time to spoilage</span><strong>{state?.tts_expected_h == null ? '—' : `${state.tts_expected_h.toFixed(1)} h`}</strong><small>Expected · {state?.tts_optimistic_h?.toFixed(0) ?? '—'}–{state?.tts_pessimistic_h?.toFixed(0) ?? '—'} h band</small></div><div className="detail-stat"><span className="mkt-symbol">MKT</span><span>Mean kinetic temp.</span><strong>{state?.mkt_c == null ? '—' : `${state.mkt_c.toFixed(1)}°C`}</strong></div></div>
    <div className="detail-grid"><section className="detail-section chart-section"><div className="section-title"><div><h3>Temperature history</h3><span>{firstTime ? new Date(firstTime).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Waiting for readings'}{lastTime ? ` — ${new Date(lastTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}</span></div><div className="safe-band-key"><i /> Safe temperature band</div></div><ErrorBoundary title="Temperature chart"><TelemetryChart points={telemetry} /></ErrorBoundary></section>
      <section className="detail-section"><div className="section-title"><div><h3>Kinetic stress</h3><span>Reference-equivalent hours consumed</span></div></div><div className="stress-visual"><div className="stress-meter"><span style={{ width: `${Math.min(100, Math.max(0, 100 - (state?.rsl_pct ?? 0)))}%` }} /></div><div className="stress-values"><span>Life consumed <b>{state?.life_consumed_h?.toFixed(1) ?? '—'} h</b></span><span>Remaining <b>{state?.rsl_h?.toFixed(1) ?? '—'} h</b></span></div><div className="expiry-compare"><div><span>Nominal expiry*</span><strong>{detail?.nominal_expiry_ts ? new Date(detail.nominal_expiry_ts).toLocaleDateString() : 'Not available'}</strong></div><ArrowRight size={16} /><div><span>Dynamic expiry estimate</span><strong>{dynamicExpiry ?? (state?.tts_expected_h == null ? 'Not available' : `${state.tts_expected_h.toFixed(0)}h remaining`)}</strong></div></div><small className="baseline-note">*Nominal estimate assumes product remains at its reference temperature from the first recorded reading.</small></div></section>
    </div>
    <section className="detail-section excursion-section"><div className="section-title"><div><h3>Excursion timeline</h3><span>Temperature events outside the product’s approved band</span></div><span className="count-pill">{detail?.excursions?.length ?? 0} events</span></div>{(detail?.excursions?.length ?? 0) === 0 ? <div className="no-excursions"><span><Thermometer size={15} /></span>No excursions recorded in this shipment history.</div> : <div className="excursion-list">{detail?.excursions?.map((event) => <article key={event.id}><div className="excursion-marker"><AlertTriangle size={15} /></div><div><strong>{event.rule_breached ?? 'Temperature excursion'}</strong><span>{new Date(event.start_ts).toLocaleString()} · Peak {event.peak_temp.toFixed(1)}°C</span></div><b>{event.duration_min.toFixed(0)} min</b></article>)}</div>}</section>
  </section></div>
}
