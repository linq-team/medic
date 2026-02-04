import { Sun, Moon, Monitor, RotateCcw, RefreshCw, Palette } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useTheme } from '@/components/theme-provider'
import {
  useSettings,
  refreshIntervalOptions,
  type RefreshInterval,
} from '@/components/settings-provider'
import { cn } from '@/lib/utils'

type Theme = 'light' | 'dark' | 'system'

const themeOptions: { value: Theme; label: string; icon: React.ReactNode; description: string }[] = [
  {
    value: 'light',
    label: 'Light',
    icon: <Sun className="h-4 w-4" />,
    description: 'Light background with dark text',
  },
  {
    value: 'dark',
    label: 'Dark',
    icon: <Moon className="h-4 w-4" />,
    description: 'Dark background with light text',
  },
  {
    value: 'system',
    label: 'System',
    icon: <Monitor className="h-4 w-4" />,
    description: 'Follow system preference',
  },
]

/**
 * Settings page component for configuring UI preferences
 */
export function Settings() {
  const { theme, setTheme } = useTheme()
  const { refreshInterval, setRefreshInterval, resetToDefaults } = useSettings()

  const handleRefreshIntervalChange = (value: string) => {
    setRefreshInterval(Number(value) as RefreshInterval)
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Settings</h1>
      <p className="text-muted-foreground mb-8">
        Configure your UI preferences and application behavior
      </p>

      <div className="space-y-6 max-w-2xl">
        {/* Theme Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="h-5 w-5" />
              Appearance
            </CardTitle>
            <CardDescription>
              Choose how Medic UI looks on your device
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              {themeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setTheme(option.value)}
                  className={cn(
                    'flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors',
                    theme === option.value
                      ? 'border-primary bg-primary/5'
                      : 'border-input hover:bg-accent hover:border-accent-foreground/20'
                  )}
                >
                  <div
                    className={cn(
                      'flex items-center justify-center w-10 h-10 rounded-full',
                      theme === option.value
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                    )}
                  >
                    {option.icon}
                  </div>
                  <span className="text-sm font-medium">{option.label}</span>
                  <span className="text-xs text-muted-foreground text-center">
                    {option.description}
                  </span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Auto-Refresh Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              Auto-Refresh
            </CardTitle>
            <CardDescription>
              Automatically refresh dashboard and list data at regular intervals
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              <label htmlFor="refresh-interval" className="text-sm font-medium">
                Refresh Interval
              </label>
              <Select
                value={refreshInterval.toString()}
                onValueChange={handleRefreshIntervalChange}
              >
                <SelectTrigger id="refresh-interval" className="w-full sm:w-[200px]">
                  <SelectValue placeholder="Select interval" />
                </SelectTrigger>
                <SelectContent>
                  {refreshIntervalOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value.toString()}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground mt-1">
                {refreshInterval === 0
                  ? 'Auto-refresh is disabled. Data will only update when you manually refresh.'
                  : `Data will automatically refresh every ${refreshInterval / 1000} seconds.`}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Reset to Defaults */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RotateCcw className="h-5 w-5" />
              Reset Settings
            </CardTitle>
            <CardDescription>
              Restore all settings to their default values
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              onClick={resetToDefaults}
              className="flex items-center gap-2"
            >
              <RotateCcw className="h-4 w-4" />
              Reset to Defaults
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              This will reset auto-refresh interval to 30 seconds. Theme preference is managed separately.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
