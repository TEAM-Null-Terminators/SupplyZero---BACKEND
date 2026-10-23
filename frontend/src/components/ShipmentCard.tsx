import { ArrowUpRight, MapPin, Thermometer } from 'lucide-react'
import type { Health, Shipment } from '../types'
import { RslRing } from './RslRing'
import { StatusBadge } from './StatusBadge'

export function ShipmentCard({ shipment, selected, onClick }: { shipment: Shipment; selected: boolean; onClick: () => void }) {
  const health = (shipment.state?.health ?? 'GREEN') as Health
  const temp = shipment.telemetry?.at(-1)?.temp_c ?? shipment.current_temp
  return <button className={`shipment-card ${selected ? 'selected' : ''}`} onClick={onClick}>
    <div className="shipment-card-top"><span className="shipment-code">{shipment.id}</span><StatusBadge health={health} /></div>
    <div className="shipment-card-body"><div className="shipment-details"><strong>{shipment.product ?? shipment.category ?? 'Temperature-sensitive goods'}</strong><span><MapPin size={12} />{shipment.status === 'QUARANTINED' ? 'Quality hold' : 'In transit'} <i /> {shipment.quantity_kg ? `${Math.round(shipment.quantity_kg)} kg` : '—'}</span><span><Thermometer size={12} />{temp == null ? '—' : `${Number(temp).toFixed(1)}°C`} <i /> MKT {shipment.state?.mkt_c == null ? '—' : `${shipment.state.mkt_c.toFixed(1)}°C`}</span></div><RslRing value={shipment.state?.rsl_pct ?? 0} health={health} /></div>
    <div className="shipment-card-foot"><span>Remaining life <b>{shipment.state?.rsl_h == null ? '—' : `${shipment.state.rsl_h.toFixed(0)}h`}</b></span><span>Time to spoilage <b>{shipment.state?.tts_expected_h == null ? '—' : `${shipment.state.tts_expected_h.toFixed(0)}h`}</b></span><ArrowUpRight size={14} /></div>
  </button>
}
