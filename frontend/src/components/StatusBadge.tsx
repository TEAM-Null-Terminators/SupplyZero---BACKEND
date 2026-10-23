import { Check, CircleAlert, ShieldAlert } from 'lucide-react'
import type { Health } from '../types'

const config = {
  GREEN: { label: 'On track', icon: Check },
  AMBER: { label: 'At risk', icon: CircleAlert },
  RED: { label: 'Critical', icon: ShieldAlert },
}

export function StatusBadge({ health = 'GREEN' }: { health?: Health }) {
  const item = config[health] ?? config.GREEN
  const Icon = item.icon
  return <span className={`status-badge status-${health.toLowerCase()}`}><Icon size={12} strokeWidth={2.6} />{item.label}</span>
}
