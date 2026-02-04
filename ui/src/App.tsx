import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/layout'
import {
  Dashboard,
  Services,
  Alerts,
  Playbooks,
  AuditLogs,
  Settings,
  Login,
} from '@/pages'

function App() {
  return (
    <Routes>
      {/* Login route - standalone without Layout */}
      <Route path="/login" element={<Login />} />

      {/* Protected routes with Layout */}
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/services" element={<Services />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/playbooks" element={<Playbooks />} />
        <Route path="/audit-logs" element={<AuditLogs />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
