import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Locale = 'en' | 'hi'
const copy = {
  en: { overview: 'Fleet overview', shipments: 'Shipments', recommendations: 'Recommendations', impact: 'Impact analytics', scenarios: 'Scenario controls', operations: 'OPERATIONS', insights: 'INSIGHTS', language: 'Language', theme: 'Toggle color theme', active: 'Active shipments', risk: 'At-risk shipments', saved: 'Value saved today', co2: 'CO₂e avoided', search: 'Search shipments...', all: 'All loads', noMatches: 'No matching shipments', tryFilter: 'Try another search or filter.', viewAll: 'View all shipments', fleetTitle: 'Shipment overview', liveFleet: 'LIVE FLEET', command: 'COMMAND CENTER', greeting: 'Good morning, Riya', subtitle: 'Here’s what’s happening across your cold-chain network today.', impactReport: 'Impact report', runScenario: 'Run a scenario', online: 'Live stream', connecting: 'Connecting', demo: 'Demo stream', shipmentSubtitle: 'Search, filter, and inspect every active shipment.', recSubtitle: 'Review deterministic recommendations and record your decision.', impactSubtitle: 'Track value recovered, food and medicine diverted, and emissions avoided.', scenariosSubtitle: 'Inject a controlled event and observe the fleet response.', back: 'Swipe left or right to move between pages.' },
  hi: { overview: 'बेड़ा अवलोकन', shipments: 'शिपमेंट', recommendations: 'सिफारिशें', impact: 'प्रभाव विश्लेषण', scenarios: 'परिदृश्य नियंत्रण', operations: 'संचालन', insights: 'अंतर्दृष्टि', language: 'भाषा', theme: 'रंग थीम बदलें', active: 'सक्रिय शिपमेंट', risk: 'जोखिम वाले शिपमेंट', saved: 'आज बचाया गया मूल्य', co2: 'CO₂e बचाया', search: 'शिपमेंट खोजें...', all: 'सभी लोड', noMatches: 'कोई शिपमेंट नहीं मिला', tryFilter: 'दूसरी खोज या फ़िल्टर आज़माएँ।', viewAll: 'सभी शिपमेंट देखें', fleetTitle: 'शिपमेंट अवलोकन', liveFleet: 'लाइव बेड़ा', command: 'कमांड सेंटर', greeting: 'सुप्रभात, रिया', subtitle: 'आज आपकी कोल्ड-चेन में क्या हो रहा है।', impactReport: 'प्रभाव रिपोर्ट', runScenario: 'परिदृश्य चलाएँ', online: 'लाइव स्ट्रीम', connecting: 'कनेक्ट हो रहा है', demo: 'डेमो स्ट्रीम', shipmentSubtitle: 'सक्रिय शिपमेंट खोजें, फ़िल्टर करें और देखें।', recSubtitle: 'नियम-आधारित सिफारिशें देखें और निर्णय दर्ज करें।', impactSubtitle: 'बचाए गए मूल्य, उत्पाद और उत्सर्जन देखें।', scenariosSubtitle: 'नियंत्रित घटना डालें और बेड़े की प्रतिक्रिया देखें।', back: 'पृष्ठ बदलने के लिए बाएँ या दाएँ स्वाइप करें।' },
} satisfies Record<Locale, Record<string, string>>

type I18nValue = { locale: Locale; setLocale: (locale: Locale) => void; t: (key: keyof typeof copy.en) => string }
const I18nContext = createContext<I18nValue | null>(null)
export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => localStorage.getItem('supplyzero-locale') === 'hi' ? 'hi' : 'en')
  useEffect(() => { localStorage.setItem('supplyzero-locale', locale) }, [locale])
  const value = useMemo(() => ({ locale, setLocale, t: (key: keyof typeof copy.en) => copy[locale][key] }), [locale])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
export function useI18n() { const value = useContext(I18nContext); if (!value) throw new Error('useI18n must be used inside I18nProvider'); return value }
