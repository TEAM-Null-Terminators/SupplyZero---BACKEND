import type { Health } from '../types'

const COLORS: Record<Health, string> = { GREEN: '#10b981', AMBER: '#f59e0b', RED: '#ef4444' }

export function RslRing({ value = 0, health = 'GREEN', size = 54 }: { value?: number; health?: Health; size?: number }) {
  const safe = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
  const stroke = 4
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  return <div className="rsl-ring" style={{ width: size, height: size }} aria-label={`${Math.round(safe)} percent remaining shelf life`}>
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}><circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e8eeeb" strokeWidth={stroke} /><circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={COLORS[health]} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - safe / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} /></svg>
    <span>{Math.round(safe)}<small>%</small></span>
  </div>
}
