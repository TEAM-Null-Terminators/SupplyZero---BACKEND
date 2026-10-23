import type { ReactNode } from 'react'
import { ArrowUpRight } from 'lucide-react'

export function MetricCard({ label, value, note, icon, accent = 'green' }: { label: string; value: string; note: string; icon: ReactNode; accent?: string }) {
  return <div className="metric-card"><div className={`metric-icon ${accent}`}>{icon}</div><div className="metric-copy"><span>{label}</span><strong>{value}</strong><small><ArrowUpRight size={12} />{note}</small></div></div>
}
