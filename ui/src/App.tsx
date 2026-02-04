import { Routes, Route } from 'react-router-dom'
import { Header } from '@/components/header'
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
        <Header />

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
