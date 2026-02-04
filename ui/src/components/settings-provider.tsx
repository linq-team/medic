import { createContext, useContext, useState, useMemo, useCallback } from 'react'

/**
 * Auto-refresh interval options in milliseconds
 * 0 = disabled
 */
export type RefreshInterval = 0 | 15000 | 30000 | 60000

export interface SettingsState {
  refreshInterval: RefreshInterval
}

export interface SettingsContextType extends SettingsState {
  setRefreshInterval: (interval: RefreshInterval) => void
  resetToDefaults: () => void
}

const STORAGE_KEY = 'medic-ui-settings'

const defaultSettings: SettingsState = {
  refreshInterval: 30000, // 30 seconds default
}

/**
 * Load settings from localStorage, falling back to defaults
 */
function loadSettings(): SettingsState {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored) as Partial<SettingsState>
      return {
        ...defaultSettings,
        ...parsed,
      }
    }
  } catch {
    // Invalid JSON or other error, use defaults
  }
  return defaultSettings
}

/**
 * Save settings to localStorage
 */
function saveSettings(settings: SettingsState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // localStorage not available or quota exceeded
  }
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined)

interface SettingsProviderProps {
  children: React.ReactNode
}

export function SettingsProvider({ children }: SettingsProviderProps) {
  const [settings, setSettings] = useState<SettingsState>(loadSettings)

  const setRefreshInterval = useCallback((interval: RefreshInterval) => {
    setSettings((prev) => {
      const newSettings = { ...prev, refreshInterval: interval }
      saveSettings(newSettings)
      return newSettings
    })
  }, [])

  const resetToDefaults = useCallback(() => {
    setSettings(defaultSettings)
    saveSettings(defaultSettings)
  }, [])

  const value = useMemo<SettingsContextType>(
    () => ({
      ...settings,
      setRefreshInterval,
      resetToDefaults,
    }),
    [settings, setRefreshInterval, resetToDefaults]
  )

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const context = useContext(SettingsContext)
  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider')
  }
  return context
}

/**
 * Human-readable labels for refresh intervals
 */
export const refreshIntervalOptions: { value: RefreshInterval; label: string }[] = [
  { value: 0, label: 'Disabled' },
  { value: 15000, label: '15 seconds' },
  { value: 30000, label: '30 seconds' },
  { value: 60000, label: '60 seconds' },
]
