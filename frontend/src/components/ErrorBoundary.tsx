import React from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

interface Props { children: React.ReactNode; title?: string }
interface State { failed: boolean }

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error: Error) { console.error('Dashboard widget failed:', error) }
  render() {
    if (!this.state.failed) return this.props.children
    return <div className="widget-error"><AlertTriangle size={18} /><strong>{this.props.title ?? 'This panel'} could not load</strong><span>Other dashboard panels are still available.</span><button onClick={() => this.setState({ failed: false })}><RotateCcw size={14} /> Try again</button></div>
  }
}
