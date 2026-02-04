import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { ThemeToggle } from '@/components/theme-toggle'
import {
  Dashboard,
  Services,
  Alerts,
  Playbooks,
  AuditLogs,
  Settings,
} from '@/pages'

function NavLink({
  to,
  children,
}: {
  to: string
  children: React.ReactNode
}) {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link
      to={to}
      className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
      }`}
    >
      {children}
    </Link>
  )
}

function App() {
  return (
    <div className="min-h-screen bg-background font-sans">
      {/* Navigation header */}
      <header className="border-b border-border">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold text-foreground">Medic UI</h1>
            <nav className="flex items-center gap-1">
              <NavLink to="/">Dashboard</NavLink>
              <NavLink to="/services">Services</NavLink>
              <NavLink to="/alerts">Alerts</NavLink>
              <NavLink to="/playbooks">Playbooks</NavLink>
              <NavLink to="/audit-logs">Audit Logs</NavLink>
              <NavLink to="/settings">Settings</NavLink>
            </nav>
          </div>
          <ThemeToggle />
        </div>
      </header>

      {/* Main content area */}
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/services" element={<Services />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/playbooks" element={<Playbooks />} />
          <Route path="/audit-logs" element={<AuditLogs />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
