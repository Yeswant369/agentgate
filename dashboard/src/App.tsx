import { NavLink, Route, Routes } from 'react-router-dom'
import { HealthBadge } from './HealthBadge'
import { AuditChain, Decisions, Metrics, Overview, Playground } from './pages'

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/decisions', label: 'Decisions' },
  { to: '/metrics', label: 'Metrics' },
  { to: '/audit', label: 'Audit Chain' },
  { to: '/playground', label: 'Playground' },
]

export default function App() {
  return (
    <div className="layout">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">⛩</span> AgentGate
          <span className="tagline">every money action explainable, bounded and gated</span>
        </div>
        <HealthBadge />
      </header>
      <nav className="nav">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="content">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/audit" element={<AuditChain />} />
          <Route path="/playground" element={<Playground />} />
        </Routes>
      </main>
    </div>
  )
}
