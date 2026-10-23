import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { Navigation } from 'lucide-react'
import type { Recommendation, Shipment } from '../types'

const KANPUR: [number, number] = [26.4499, 80.3319]
const LUCKNOW: [number, number] = [26.8467, 80.9462]
const hubs = [{ name: 'Kanpur Cold Hub', pos: KANPUR }, { name: 'Lucknow Retail Hub', pos: LUCKNOW }]

function TruckIcon({ color }: { color: string }) {
  return L.divIcon({ className: 'truck-marker-wrap', html: `<div class="truck-marker" style="--marker:${color}"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h11v11H3zM14 10h4l3 3v4h-7z"/><circle cx="7.5" cy="18" r="1.5"/><circle cx="17.5" cy="18" r="1.5"/></svg></div>`, iconSize: [38, 38], iconAnchor: [19, 19] })
}

function FitFleet({ shipments }: { shipments: Shipment[] }) {
  const map = useMap()
  useEffect(() => {
    const points = shipments.filter((s) => Number.isFinite(s.current_lat) && Number.isFinite(s.current_lon)).map((s) => [s.current_lat!, s.current_lon!] as [number, number])
    if (points.length > 0) map.fitBounds(L.latLngBounds(points).pad(0.24), { maxZoom: 9, animate: true })
  }, [map, shipments.length])
  return null
}

export function FleetMap({ shipments, recommendations, onSelect }: { shipments: Shipment[]; recommendations: Recommendation[]; onSelect: (id: string) => void }) {
  const routeRef = useRef<L.Polyline | null>(null)
  const critical = useMemo(() => shipments.find((item) => item.state?.health === 'AMBER' || item.state?.health === 'RED'), [shipments])
  const coords = (shipment: Shipment) => Number.isFinite(shipment.current_lat) && Number.isFinite(shipment.current_lon) ? [shipment.current_lat!, shipment.current_lon!] as [number, number] : null
  const routeStart = critical ? coords(critical) : null
  const showRoute = recommendations.some((r) => r.status === 'PENDING' && r.action === 'REROUTE') && routeStart

  useEffect(() => () => { routeRef.current?.remove(); routeRef.current = null }, [])

  return <div className="map-shell">
    <MapContainer center={KANPUR} zoom={8} scrollWheelZoom className="fleet-map" zoomControl={false} preferCanvas>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <FitFleet shipments={shipments} />
      {shipments.map((shipment) => {
        const position = coords(shipment)
        if (!position) return null
        const tone = shipment.state?.health === 'RED' ? '#ef4444' : shipment.state?.health === 'AMBER' ? '#f59e0b' : '#10b981'
        return <Marker key={shipment.id} position={position} icon={TruckIcon({ color: tone })} eventHandlers={{ click: () => onSelect(shipment.id) }}>
          <Tooltip direction="top" offset={[0, -16]}><strong>{shipment.id}</strong><br />{shipment.product ?? 'Cold-chain load'} · {Math.round(shipment.state?.rsl_pct ?? 0)}% life left</Tooltip>
        </Marker>
      })}
      {hubs.map((hub) => <CircleMarker key={hub.name} center={hub.pos} radius={7} pathOptions={{ color: '#426c5d', fillColor: '#ffffff', fillOpacity: 1, weight: 3 }}><Tooltip>{hub.name}</Tooltip></CircleMarker>)}
      {showRoute && <Polyline ref={(layer) => { routeRef.current = layer }} positions={[routeStart!, KANPUR]} pathOptions={{ color: '#176b54', weight: 4, dashArray: '9 10', className: 'route-dash', opacity: 0.9 }} />}
    </MapContainer>
    <div className="map-top-label"><span className="live-dot" /> FLEET LIVE MAP <span>·</span> Kanpur–Lucknow corridor</div>
    <div className="map-legend"><span><i className="legend-dot safe" />Healthy</span><span><i className="legend-dot warning" />At risk</span><span><i className="legend-dot critical" />Critical</span><span><i className="hub-mark" />Cold hub</span></div>
    {showRoute && <div className="map-route-chip"><Navigation size={14} /> Recommended reroute</div>}
  </div>
}
