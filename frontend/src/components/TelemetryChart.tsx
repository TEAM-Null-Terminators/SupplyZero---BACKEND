import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TelemetryPoint } from '../types'

export function TelemetryChart({ points, safeMin = 2, safeMax = 8 }: { points: TelemetryPoint[]; safeMin?: number; safeMax?: number }) {
  const data = points.slice(-200).map((point) => ({ ...point, label: new Date(point.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }))
  return <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 14, right: 14, left: -20, bottom: 0 }}>
    <CartesianGrid stroke="#edf1ef" vertical={false} />
    <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: '#95a19b', fontSize: 10 }} minTickGap={24} />
    <YAxis domain={['auto', 'auto']} tickLine={false} axisLine={false} tick={{ fill: '#95a19b', fontSize: 10 }} unit="°" />
    <ReferenceArea y1={safeMin} y2={safeMax} fill="#10b981" fillOpacity={0.08} />
    <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #e4ebe7', boxShadow: '0 6px 20px #203a2b10' }} labelStyle={{ color: '#718078', fontSize: 11 }} formatter={(value) => [`${value} °C`, 'Temperature']} />
    <Line type="monotone" dataKey="temp_c" stroke="#167456" strokeWidth={2.4} dot={false} activeDot={{ r: 4, fill: '#167456', stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false} />
  </LineChart></ResponsiveContainer></div>
}
