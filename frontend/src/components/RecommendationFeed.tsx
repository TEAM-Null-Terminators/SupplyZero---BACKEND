import { useState } from 'react'
import { ArrowDownRight, ArrowUpRight, Check, Clock3, CornerUpRight, LoaderCircle, ShieldAlert, X } from 'lucide-react'
import type { Recommendation } from '../types'

function money(value = 0) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value) }

export function RecommendationFeed({ items, onAction }: { items: Recommendation[]; onAction: (id: string, action: 'approve' | 'reject') => Promise<void> }) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')
  const pending = items.filter((item) => item.status === 'PENDING').slice(0, 6)
  const act = async (id: string, action: 'approve' | 'reject') => {
    setError(''); setBusy(id)
    try { await onAction(id, action) } catch (e) { setError(e instanceof Error ? e.message : 'Action could not be completed') } finally { setBusy(null) }
  }
  return <section className="panel recommendation-panel">
    <div className="panel-heading"><div><span className="eyebrow">DECISION ENGINE</span><h2>Agent recommendations <span className="count-pill">{pending.length}</span></h2></div><button className="text-button">View all <ArrowUpRight size={14} /></button></div>
    {error && <div className="inline-error">{error}</div>}
    {pending.length === 0 ? <div className="empty-state"><Check size={21} /><strong>All clear</strong><span>No pending decisions need your attention.</span></div> : <div className="recommendation-list">{pending.map((item) => {
      const quarantine = item.action === 'QUARANTINE'
      const Icon = quarantine ? ShieldAlert : CornerUpRight
      return <article className={`recommendation-card ${quarantine ? 'quarantine-card' : ''}`} key={item.id}>
        <div className="rec-icon"><Icon size={17} /></div>
        <div className="rec-main"><div className="rec-title-row"><strong>{quarantine ? 'QA quarantine required' : `${item.action === 'REROUTE' ? 'Reroute' : 'Clearance'} recommended`}</strong><span className="rec-time"><Clock3 size={11} />{new Date(item.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></div>
          <span className="rec-shipment">{item.shipment_id} <i /> {item.target_hub_name ?? (quarantine ? 'Quality review' : 'Best available hub')}</span>
          <p>{item.rationale || `${item.action === 'REROUTE' ? 'Rerouting' : 'Reviewing'} shipment ${item.shipment_id} protects remaining product life and reduces waste.`}</p>
          <div className="rec-bottom"><span className="saving"><ArrowDownRight size={14} />{item.saving != null ? money(item.saving) : 'Value protected'}</span>{item.co2e_avoided ? <span className="co2-note">{item.co2e_avoided.toFixed(0)} kg CO₂e avoided</span> : null}</div>
          <div className="rec-actions"><button disabled={busy === item.id} onClick={() => act(item.id, 'approve')} className="approve-btn">{busy === item.id ? <LoaderCircle size={14} className="spin" /> : <Check size={14} />}{quarantine ? 'Acknowledge QA' : 'Approve action'}</button><button disabled={busy === item.id} onClick={() => act(item.id, 'reject')} className="reject-btn"><X size={14} />Reject</button></div>
        </div>
      </article>
    })}</div>}
  </section>
}
