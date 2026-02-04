import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { ThemeToggle } from '@/components/theme-toggle'
import { useTheme } from '@/components/theme-provider'

function App() {
  const { theme } = useTheme()

  return (
    <div className="min-h-screen flex items-center justify-center bg-background font-sans p-8">
      <div className="text-center max-w-4xl">
        {/* Theme toggle in top right */}
        <div className="fixed top-4 right-4 flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            Theme: {theme}
          </span>
          <ThemeToggle />
        </div>

        <h1 className="text-4xl font-bold text-primary mb-4">Medic UI</h1>
        <p className="text-lg text-foreground">Heartbeat Monitoring Service</p>
        <p className="text-sm text-muted-foreground mt-2">UI Coming Soon</p>
        <p className="font-mono text-sm text-foreground mt-4 bg-muted px-4 py-2 rounded">
          font-mono: Geist Mono for code and numerals
        </p>

        {/* Status badges */}
        <div className="mt-8 flex gap-2 justify-center flex-wrap">
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

        {/* shadcn/ui Button variants */}
        <div className="mt-8 flex gap-3 justify-center flex-wrap">
          <Button>Default</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="link">Link</Button>
        </div>

        {/* shadcn/ui Card component */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Services</CardTitle>
              <CardDescription>Monitor your registered services</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-mono font-semibold text-status-healthy">
                12 Active
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Alerts</CardTitle>
              <CardDescription>Current active alerts</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-mono font-semibold text-status-error">
                3 Active
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default App
