import { useState } from 'react'
import { Activity, CloudSun, DoorOpen, Snowflake, ThermometerSnowflake, WifiOff, X, LoaderCircle } from 'lucide-react'

const scenarios = [
  { id: 'compressor_failure', label: 'Compressor failure', detail: 'Cooling stops; cargo warms steadily', icon: ThermometerSnowflake, tone: 'orange' },
  { id: 'freeze', label: 'Freeze event', detail: 'Temperature drops below 0°C', icon: Snowflake, tone: 'blue' },
  { id: 'door_open', label: 'Door left open', detail: 'Short warm-air exposure', icon: DoorOpen, tone: 'amber' },
  { id: 'heatwave', label: 'Heatwave', detail: 'Ambient temperature rises to 42°C', icon: CloudSun, tone: 'red' },
  { id: 'sensor_dropout', label: 'Telemetry gap', detail: 'Simulate a logger going offline', icon: WifiOff, tone: 'gray' },
]

export function ScenarioDrawer({ open, shipments, onClose, onInject, initialShipmentId = '' }: { open: boolean; shipments: { id: string; product?: string }[]; onClose: () => void; onInject: (shipmentId: string, scenario: string) => Promise<void>; initialShipmentId?: string }) {
  const [selected, setSelected] = useState('')
  const [shipmentId, setShipmentId] = useState(initialShipmentId)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  if (!open) return null
  const inject = async (scenario: string) => {
    if (!shipmentId) { setMessage('Choose a shipment first.'); return }
    setSelected(scenario); setBusy(true); setMessage('')
    try { await onInject(shipmentId, scenario); setMessage('Scenario sent to the engine. Watch the fleet update.') }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Could not inject scenario.') }
    finally { setBusy(false) }
  }
  return <div className="drawer-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}><aside className="scenario-drawer" aria-label="Demo scenario controls"><header><div className="drawer-icon"><Activity size={18} /></div><div><span className="eyebrow">DEMO CONTROL</span><h2>Inject a scenario</h2></div><button className="icon-button" onClick={onClose} aria-label="Close scenario drawer"><X size={19} /></button></header><p className="drawer-intro">Send a controlled thermal event to a shipment and observe how SupplyZero reacts.</p>
    <label className="field-label" htmlFor="scenario-shipment">Target shipment</label><select id="scenario-shipment" value={shipmentId} onChange={(e) => setShipmentId(e.target.value)}><option value="">Select a shipment…</option>{shipments.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.product ?? 'Shipment'}</option>)}</select>
    <div className="scenario-options">{scenarios.map((scenario) => { const Icon = scenario.icon; return <button key={scenario.id} className={`scenario-option ${selected === scenario.id ? 'active' : ''}`} disabled={busy} onClick={() => inject(scenario.id)}><span className={`scenario-icon ${scenario.tone}`}><Icon size={18} /></span><span><strong>{scenario.label}</strong><small>{scenario.detail}</small></span>{busy && selected === scenario.id ? <LoaderCircle size={16} className="spin scenario-arrow" /> : <span className="scenario-arrow">↗</span>}</button> })}</div>
    {message && <div className={`scenario-message ${message.includes('Choose') || message.includes('Could') ? 'error' : ''}`}>{message}</div>}
    <div className="drawer-foot"><span className="live-dot" />Connected to local simulation</div>
  </aside></div>
}
