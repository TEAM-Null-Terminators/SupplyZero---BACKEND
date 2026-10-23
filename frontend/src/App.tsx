import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Boxes, Check, ChevronDown, CircleHelp, Cloud, Leaf, Languages, Menu, Moon, Plus, Radio, Search, ShieldCheck, SlidersHorizontal, Sun, Truck, X } from 'lucide-react'
import { api } from './services/api'
import { useFleetStore } from './store/fleetStore'
import { useResilientWebSocket } from './hooks/useResilientWebSocket'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ShipmentCard } from './components/ShipmentCard'
import { MetricCard } from './components/MetricCard'
import type { ShipmentDetail } from './types'
import { useI18n } from './i18n'

const FleetMap = lazy(() => import('./components/FleetMap').then((module) => ({ default: module.FleetMap })))
const RecommendationFeed = lazy(() => import('./components/RecommendationFeed').then((module) => ({ default: module.RecommendationFeed })))
const DetailModal = lazy(() => import('./components/DetailModal').then((module) => ({ default: module.DetailModal })))
const ScenarioDrawer = lazy(() => import('./components/ScenarioDrawer').then((module) => ({ default: module.ScenarioDrawer })))
const ImpactModal = lazy(() => import('./components/ImpactModal').then((module) => ({ default: module.ImpactModal })))

const tabs = ['Fleet overview', 'Shipments', 'Recommendations', 'Impact analytics', 'Scenario controls'] as const
type Filter = 'ALL' | 'PHARMA' | 'PRODUCE' | 'DAIRY' | 'BIOLOGIC'

export default function App() {
  const { locale, setLocale, t } = useI18n()
  useResilientWebSocket()
  const queryClient = useQueryClient()
  const shipments = useFleetStore((state) => state.shipments)
  const recommendations = useFleetStore((state) => state.recommendations)
  const telemetry = useFleetStore((state) => state.telemetry)
  const setShipments = useFleetStore((state) => state.setShipments)
  const setRecommendations = useFleetStore((state) => state.setRecommendations)
  const setTelemetry = useFleetStore((state) => state.setTelemetry)
  const applyDemoScenario = useFleetStore((state) => state.applyDemoScenario)
  const connection = useFleetStore((state) => state.wsStatus)
  const offlineMode = useFleetStore((state) => state.offlineMode)
  const [filter, setFilter] = useState<Filter>('ALL')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [scenarioOpen, setScenarioOpen] = useState(false)
  const [impactOpen, setImpactOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>('Fleet overview')
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('supplyzero-theme') === 'dark')
  const touchStart = useRef<{ x: number; y: number } | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [toast, setToast] = useState('')

  const fleetQuery = useQuery({ queryKey: ['shipments'], queryFn: api.shipments, refetchInterval: 60_000 })
  const recommendationQuery = useQuery({ queryKey: ['recommendations'], queryFn: api.recommendations, refetchInterval: 15_000 })
  const impactQuery = useQuery({ queryKey: ['impact'], queryFn: api.impact, refetchInterval: 30_000 })
  const detailQuery = useQuery({ queryKey: ['shipment', selectedId], queryFn: () => api.shipment(selectedId!), enabled: Boolean(selectedId), retry: false })
  const telemetryQuery = useQuery({ queryKey: ['telemetry', selectedId], queryFn: () => api.telemetry(selectedId!), enabled: Boolean(selectedId), retry: false, refetchInterval: selectedId ? 15_000 : false })

  useEffect(() => { if (fleetQuery.data) setShipments(fleetQuery.data) }, [fleetQuery.data, setShipments])
  useEffect(() => { if (recommendationQuery.data) setRecommendations(recommendationQuery.data) }, [recommendationQuery.data, setRecommendations])
  useEffect(() => { if (selectedId && telemetryQuery.data) setTelemetry(selectedId, telemetryQuery.data) }, [selectedId, telemetryQuery.data, setTelemetry])
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 3500); return () => window.clearTimeout(timer) }, [toast])
  useEffect(() => { document.documentElement.dataset.theme = darkMode ? 'dark' : 'light'; localStorage.setItem('supplyzero-theme', darkMode ? 'dark' : 'light') }, [darkMode])
  useEffect(() => {
    const nodes = document.querySelectorAll<HTMLElement>('.scroll-reveal')
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { nodes.forEach((node) => node.classList.add('is-visible')); return }
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target) } }), { threshold: 0.08 })
    nodes.forEach((node) => observer.observe(node))
    return () => observer.disconnect()
  }, [activeTab, shipments.length, recommendations.length])

  const visibleShipments = useMemo(() => shipments.filter((shipment) => {
    const matchesFilter = filter === 'ALL' || (shipment.category ?? '').toUpperCase() === filter || (filter === 'PHARMA' && /vaccine|insulin|pharma|biologic/i.test(shipment.product ?? '')) || (filter === 'PRODUCE' && /berry|berries|green|produce|fruit/i.test(shipment.product ?? ''))
    const matchesSearch = `${shipment.id} ${shipment.product ?? ''} ${shipment.status ?? ''}`.toLowerCase().includes(search.toLowerCase())
    return matchesFilter && matchesSearch
  }), [shipments, filter, search])
  const activeCount = shipments.filter((item) => item.status !== 'QUARANTINED').length
  const riskCount = shipments.filter((item) => item.state?.health === 'AMBER' || item.state?.health === 'RED').length
  const atRiskValue = recommendations.filter((item) => item.status === 'PENDING').reduce((sum, item) => sum + Math.max(0, item.baseline_value ?? 0), 0)
  const impact = impactQuery.data ?? (offlineMode ? { value_saved: 48_200, co2e_avoided_kg: 236, kg_diverted: 1_480, baseline_value: 180_000, supplyzero_value: 228_200 } : undefined)
  const selected = shipments.find((item) => item.id === selectedId)
  const selectedDetail: ShipmentDetail | undefined = detailQuery.data ?? (selected ? { shipment: selected, state: selected.state, excursions: [] } : undefined)

  const handleRecommendation = async (id: string, action: 'approve' | 'reject') => {
    if (fleetQuery.isError || id.startsWith('demo-')) {
      setRecommendations(recommendations.map((item) => item.id === id ? { ...item, status: action === 'approve' ? 'APPROVED' : 'REJECTED' } : item))
      setToast(action === 'approve' ? 'Decision approved in demo mode.' : 'Recommendation dismissed.')
      return
    }
    await (action === 'approve' ? api.approve(id) : api.reject(id))
    await Promise.all([queryClient.invalidateQueries({ queryKey: ['recommendations'] }), queryClient.invalidateQueries({ queryKey: ['impact'] })])
    setToast(action === 'approve' ? 'Decision approved and audit logged.' : 'Recommendation rejected and audit logged.')
  }
  const handleScenario = async (shipmentId: string, scenario: string) => {
    if (fleetQuery.isError) { applyDemoScenario(shipmentId, scenario); setToast('Offline demo scenario applied.'); return }
    await api.scenario(shipmentId, scenario)
    await queryClient.invalidateQueries({ queryKey: ['shipments'] })
    await queryClient.invalidateQueries({ queryKey: ['recommendations'] })
  }
  const quarantine = async () => {
    if (!selectedId) return
    if (fleetQuery.isError) { applyDemoScenario(selectedId, 'freeze'); setToast('Shipment flagged for QA review in demo mode.'); return }
    await api.quarantine(selectedId)
    await Promise.all([queryClient.invalidateQueries({ queryKey: ['shipments'] }), queryClient.invalidateQueries({ queryKey: ['recommendations'] })])
    setToast('Shipment quarantined. QA review required.')
  }

  return <div className="app-shell">
    {mobileNavOpen && <button className="mobile-nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
    <aside className={`sidebar ${mobileNavOpen ? 'mobile-open' : ''}`}><div className="brand-lockup"><div className="brand-mark"><img src="/supplyzero-leaf.png" alt="" /></div><div><strong>SupplyZero</strong><span>Cold-chain intelligence</span></div><button className="mobile-nav-close" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><X size={18} /></button></div>
      <div className="workspace-selector"><span className="workspace-avatar">N</span><span><small>WORKSPACE</small><b>Northstar Logistics</b></span><ChevronDown size={15} /></div>
      <div className="nav-label">{t('operations')}</div><nav className="main-nav">{tabs.slice(0, 3).map((tab, index) => { const Icon = [Activity, Truck, Bell][index]; const key = index === 0 ? 'overview' : index === 1 ? 'shipments' : 'recommendations'; return <button key={tab} className={activeTab === tab ? 'active' : ''} onClick={() => { setActiveTab(tab); setMobileNavOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }}><Icon size={17} /><span>{t(key)}</span>{tab === 'Recommendations' && recommendations.filter((item) => item.status === 'PENDING').length > 0 && <i>{recommendations.filter((item) => item.status === 'PENDING').length}</i>}</button> })}</nav>
      <div className="nav-label tools-label">{t('insights')}</div><nav className="main-nav"><button className={activeTab === 'Impact analytics' ? 'active' : ''} onClick={() => { setActiveTab('Impact analytics'); setMobileNavOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }}><BarChart3 size={17} /><span>{t('impact')}</span></button><button className={activeTab === 'Scenario controls' ? 'active' : ''} onClick={() => { setActiveTab('Scenario controls'); setMobileNavOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }}><SlidersHorizontal size={17} /><span>{t('scenarios')}</span><span className="nav-new">DEMO</span></button></nav>
      <div className="sidebar-spacer" /><div className="side-health"><div className="side-health-top"><span><ShieldCheck size={15} /> System health</span><i className="live-dot" /></div><div className="side-health-bottom"><span className="side-uptime">{fleetQuery.isError ? 'Local demo mode' : 'All services operational'}</span><span className="side-uplink">{fleetQuery.isError ? 'API offline' : 'API connected'}</span></div></div>
      <button className="profile-button"><span className="profile-avatar">RS</span><span><b>Riya Sharma</b><small>Logistics controller</small></span><ChevronDown size={14} /></button>
    </aside>
    <main className="main-content">
      <header className="topbar"><div className="breadcrumb"><span>{t('operations')}</span><span>/</span><b>{t(activeTab === 'Fleet overview' ? 'overview' : activeTab === 'Shipments' ? 'shipments' : activeTab === 'Recommendations' ? 'recommendations' : activeTab === 'Impact analytics' ? 'impact' : 'scenarios')}</b></div><div className="topbar-actions"><span className="today-label">{new Date().toLocaleDateString(locale === 'hi' ? 'hi-IN' : 'en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}</span><label className="language-control" title={t('language')}><Languages size={15} /><select aria-label={t('language')} value={locale} onChange={(event) => setLocale(event.target.value as 'en' | 'hi')}><option value="en">EN</option><option value="hi">हिंदी</option></select></label><button className="icon-button" aria-label={t('theme')} title={t('theme')} onClick={() => setDarkMode((value) => !value)}>{darkMode ? <Sun size={17} /> : <Moon size={17} />}</button><button className="icon-button notification-button" aria-label="Notifications"><Bell size={17} /><i /></button><div className={`connection-pill ${connection}`}><span className="live-dot" />{connection === 'live' ? t('online') : connection === 'connecting' ? t('connecting') : t('demo')}</div><button className="mobile-menu" onClick={() => setMobileNavOpen(true)} aria-label="Open navigation"><Menu size={20} /></button></div></header>
      <div className="page-content" onTouchStart={(event) => { const touch = event.touches[0]; touchStart.current = { x: touch.clientX, y: touch.clientY } }} onTouchEnd={(event) => { if (!touchStart.current) return; const dx = event.changedTouches[0].clientX - touchStart.current.x; const dy = event.changedTouches[0].clientY - touchStart.current.y; touchStart.current = null; if (Math.abs(dx) < 75 || Math.abs(dy) > Math.abs(dx)) return; const order = [...tabs]; const next = Math.max(0, Math.min(order.length - 1, order.indexOf(activeTab) + (dx < 0 ? 1 : -1))); setActiveTab(order[next]) }} onPointerMove={(event) => { if (event.pointerType !== 'mouse') return; const rect = event.currentTarget.getBoundingClientRect(); event.currentTarget.style.setProperty('--pointer-x', `${event.clientX - rect.left}px`); event.currentTarget.style.setProperty('--pointer-y', `${event.clientY - rect.top}px`) }}>
      {activeTab !== 'Fleet overview' && <div className="page-heading scroll-reveal"><div><div className="greeting-line"><span className="eyebrow">{t(activeTab === 'Shipments' ? 'shipments' : activeTab === 'Recommendations' ? 'recommendations' : activeTab === 'Impact analytics' ? 'impact' : 'scenarios')}</span></div><h1>{t(activeTab === 'Shipments' ? 'shipments' : activeTab === 'Recommendations' ? 'recommendations' : activeTab === 'Impact analytics' ? 'impact' : 'scenarios')}</h1><p>{t(activeTab === 'Shipments' ? 'shipmentSubtitle' : activeTab === 'Recommendations' ? 'recSubtitle' : activeTab === 'Impact analytics' ? 'impactSubtitle' : 'scenariosSubtitle')}</p></div></div>}
      {activeTab === 'Shipments' && <section className="panel page-view scroll-reveal"><div className="workspace-head"><div><h2>{t('fleetTitle')} <span className="total-pill">{visibleShipments.length}</span></h2><p className="page-help">{t('back')}</p></div></div><div className="fleet-list-head"><div className="search-box"><Search size={15} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('search')} aria-label={t('search')} /></div><div className="filter-row">{(['ALL', 'PHARMA', 'PRODUCE', 'DAIRY'] as Filter[]).map((item) => <button key={item} className={filter === item ? 'active' : ''} onClick={() => setFilter(item)}>{item === 'ALL' ? t('all') : item.charAt(0) + item.slice(1).toLowerCase()}</button>)}</div></div><div className="shipments-grid">{visibleShipments.map((shipment) => <ShipmentCard key={shipment.id} shipment={shipment} selected={selectedId === shipment.id} onClick={() => setSelectedId(shipment.id)} />)}{visibleShipments.length === 0 && <div className="empty-fleet"><Search size={19} /><strong>{t('noMatches')}</strong><span>{t('tryFilter')}</span></div>}</div></section>}
      {activeTab === 'Recommendations' && <section className="page-view scroll-reveal"><ErrorBoundary title="Recommendation feed"><Suspense fallback={<div className="panel-loading"><span className="spinner" />Loading decision feed…</div>}><RecommendationFeed items={recommendations} onAction={handleRecommendation} /></Suspense></ErrorBoundary></section>}
      {activeTab === 'Impact analytics' && <section className="panel page-view scroll-reveal"><div className="workspace-head"><div><h2>{t('impact')}</h2><p className="page-help">{t('impactSubtitle')}</p></div></div><div className="impact-metrics"><div><span className="impact-icon money"><ArrowDownRight size={17} /></span><small>Value saved</small><strong>₹{(impact?.value_saved ?? 0).toLocaleString('en-IN')}</strong><em>approved recommendations</em></div><div><span className="impact-icon leaf"><Leaf size={17} /></span><small>CO₂e avoided</small><strong>{(impact?.co2e_avoided_kg ?? 0).toLocaleString('en-IN')}<i> kg</i></strong><em>net of extra transport</em></div><div><span className="impact-icon boxes"><Boxes size={17} /></span><small>Product diverted</small><strong>{(impact?.kg_diverted ?? 0).toLocaleString('en-IN')}<i> kg</i></strong><em>kept in the supply chain</em></div></div><button className="secondary-button" onClick={() => setImpactOpen(true)}><BarChart3 size={15} /> Open value comparison</button></section>}
      {activeTab === 'Scenario controls' && <section className="panel page-view scroll-reveal"><div className="workspace-head"><div><h2>{t('scenarios')}</h2><p className="page-help">{t('scenariosSubtitle')}</p></div></div><div className="scenario-page-grid">{shipments.map((shipment) => <article className="scenario-shipment" key={shipment.id}><div><strong>{shipment.id}</strong><span>{shipment.product ?? shipment.category ?? 'Shipment'}</span></div><button className="primary-button" onClick={() => { setSelectedId(shipment.id); setScenarioOpen(true) }}><Plus size={15} /> Choose event</button></article>)}</div></section>}
      {activeTab === 'Fleet overview' && <>
      <div className="page-heading"><div><div className="greeting-line"><span className="eyebrow">{t('command')}</span><span className="updated-label"><span className="live-dot" />UPDATED JUST NOW</span></div><h1>{t('greeting')} <span>✳</span></h1><p>{t('subtitle')}</p></div><div className="heading-actions"><button className="secondary-button" onClick={() => setActiveTab('Impact analytics')}><BarChart3 size={15} /> {t('impactReport')}</button><button className="primary-button" onClick={() => setActiveTab('Scenario controls')}><Plus size={16} /> {t('runScenario')}</button></div></div>
        <section className="metrics-grid"><MetricCard label="Active shipments" value={String(activeCount).padStart(2, '0')} note="Fleet monitored in real time" icon={<Boxes size={17} />} /><MetricCard label="At-risk shipments" value={String(riskCount).padStart(2, '0')} note={`${riskCount ? 'Needs attention now' : 'All loads on track'}`} icon={<AlertTriangle size={17} />} accent={riskCount ? 'amber' : 'green'} /><MetricCard label="Value saved today" value={`₹${(impact?.value_saved ?? atRiskValue).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} note="From recorded decisions" icon={<ArrowDownRight size={18} />} accent="green" /><MetricCard label="CO₂e avoided" value={`${(impact?.co2e_avoided_kg ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })} kg`} note="Net of added transport" icon={<Leaf size={17} />} accent="blue" /></section>
        {fleetQuery.isError && <div className="demo-banner"><Cloud size={16} /><span><b>Backend unavailable.</b> You’re viewing a live demo simulation with sample shipments.</span><button onClick={() => fleetQuery.refetch()}>Retry connection <ArrowUpRight size={13} /></button></div>}
        <section className="fleet-section"><div className="workspace-head"><div><div className="section-kicker"><span className="live-dot" />LIVE FLEET</div><h2>Shipment overview <span className="total-pill">{shipments.length}</span></h2></div><div className="fleet-head-tools"><span className="last-sync"><Radio size={13} /> Syncing every 60 sec</span><button className="icon-button filter-button" aria-label="Filter fleet"><SlidersHorizontal size={16} /></button></div></div>
          <div className="fleet-workspace"><section className="panel fleet-list-panel"><div className="fleet-list-head"><div className="search-box"><Search size={15} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search shipments..." aria-label="Search shipments" /><kbd>⌘ K</kbd></div><div className="filter-row">{(['ALL', 'PHARMA', 'PRODUCE', 'DAIRY'] as Filter[]).map((item) => <button key={item} className={filter === item ? 'active' : ''} onClick={() => setFilter(item)}>{item === 'ALL' ? 'All loads' : item.charAt(0) + item.slice(1).toLowerCase()}</button>)}</div></div>
              <div className="shipment-list">{visibleShipments.length ? visibleShipments.map((shipment) => <ShipmentCard key={shipment.id} shipment={shipment} selected={selectedId === shipment.id} onClick={() => setSelectedId(shipment.id)} />) : <div className="empty-fleet"><Search size={19} /><strong>No matching shipments</strong><span>Try another search or filter.</span></div>}</div>
              <button className="view-shipments" onClick={() => { setActiveTab('Shipments'); setFilter('ALL'); setSearch('') }}>View all shipments <ArrowUpRight size={14} /></button>
            </section>
            <div className="map-and-agent"><section className="panel map-panel"><ErrorBoundary title="Fleet map"><Suspense fallback={<div className="map-loading"><span className="spinner" />Preparing live map…</div>}><FleetMap shipments={visibleShipments} recommendations={recommendations} onSelect={setSelectedId} /></Suspense></ErrorBoundary></section><div id="recommendations"><ErrorBoundary title="Recommendation feed"><Suspense fallback={<div className="panel-loading"><span className="spinner" />Loading decision feed…</div>}><RecommendationFeed items={recommendations} onAction={handleRecommendation} /></Suspense></ErrorBoundary></div></div>
          </div>
        </section>
        <footer className="page-footer"><span>SupplyZero decision support · Illustrative kinetic profiles</span><button onClick={() => setToast('Profile values are configurable in the backend product catalog.') }><CircleHelp size={13} /> About the model</button><span className="footer-version">SYSTEM V1.0 <i /> ENCRYPTED CONNECTION</span></footer>
      </>}
      </div>
    </main>
    {selectedId && <Suspense fallback={<div className="overlay-loading"><span className="spinner" />Loading shipment details…</div>}><DetailModal detail={selectedDetail} telemetry={telemetry[selectedId] ?? []} loading={detailQuery.isLoading || telemetryQuery.isFetching} onClose={() => setSelectedId(null)} onQuarantine={quarantine} /></Suspense>}
    {scenarioOpen && <Suspense fallback={<div className="overlay-loading"><span className="spinner" />Loading controls…</div>}><ScenarioDrawer open={scenarioOpen} shipments={shipments} initialShipmentId={selectedId ?? ''} onClose={() => setScenarioOpen(false)} onInject={handleScenario} /></Suspense>}
    {impactOpen && <Suspense fallback={<div className="overlay-loading"><span className="spinner" />Loading impact report…</div>}><ImpactModal open={impactOpen} impact={impact} onClose={() => setImpactOpen(false)} /></Suspense>}
    {toast && <div role="status" className="toast"><Check size={16} />{toast}<button onClick={() => setToast('')} aria-label="Dismiss"><X size={14} /></button></div>}
  </div>
}
