import { Routes, Route } from 'react-router-dom'
import { ThemeToggle } from '@/components/theme-toggle'
import { Sidebar } from '@/components/sidebar'
import {
  Dashboard,
  Services,
  Alerts,
  Playbooks,
  AuditLogs,
  Settings,
} from '@/pages'

function App() {
  return (
    <div className="min-h-screen bg-background font-sans flex">
      {/* Sidebar navigation */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="border-b border-border bg-card">
          <div className="px-6 py-4 flex items-center justify-between">
            <h1 className="text-xl font-bold text-foreground">Medic UI</h1>
            <ThemeToggle />
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6">
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
    </div>
  )
}

export default App
