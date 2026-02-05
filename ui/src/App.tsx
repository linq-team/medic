import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/layout'
import { ProtectedRoute } from '@/components/protected-route'
import {
  Dashboard,
  Services,
  ServiceDetail,
  Alerts,
  AlertDetail,
  Playbooks,
  AuditLogs,
  History,
  Settings,
  Login,
} from '@/pages'

function App() {
  return (
    <Routes>
      {/* Login route - standalone without Layout */}
      <Route path="/login" element={<Login />} />

      {/* Protected routes with Layout */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/services" element={<Services />} />
        <Route path="/services/:id" element={<ServiceDetail />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/alerts/:id" element={<AlertDetail />} />
        <Route path="/playbooks" element={<Playbooks />} />
        <Route path="/audit-logs" element={<AuditLogs />} />
        <Route path="/history" element={<History />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
