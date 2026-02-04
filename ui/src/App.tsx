function App() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-linq-cream">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-linq-navy mb-4">Medic</h1>
        <p className="text-lg text-linq-black">Heartbeat Monitoring Service</p>
        <p className="text-sm text-linq-sage mt-2">UI Coming Soon</p>
        <div className="mt-8 flex gap-2 justify-center">
          <span className="px-3 py-1 rounded bg-status-healthy text-white text-sm">
            Healthy
          </span>
          <span className="px-3 py-1 rounded bg-status-warning text-white text-sm">
            Warning
          </span>
          <span className="px-3 py-1 rounded bg-status-error text-white text-sm">
            Error
          </span>
          <span className="px-3 py-1 rounded bg-status-critical text-white text-sm">
            Critical
          </span>
          <span className="px-3 py-1 rounded bg-status-muted text-white text-sm">
            Muted
          </span>
        </div>
      </div>
    </div>
  )
}

export default App
