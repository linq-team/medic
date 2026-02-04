import { createContext, useContext, useState, useCallback, useMemo } from 'react'
import { apiClient } from '@/lib/api'

type AuthProviderProps = {
  children: React.ReactNode
  storageKey?: string
}

type AuthContextState = {
  isAuthenticated: boolean
  apiKey: string | null
  login: (apiKey: string) => void
  logout: () => void
}

const initialState: AuthContextState = {
  isAuthenticated: false,
  apiKey: null,
  login: () => null,
  logout: () => null,
}

const AuthContext = createContext<AuthContextState>(initialState)

const STORAGE_KEY_DEFAULT = 'medic-ui-api-key'

export function AuthProvider({
  children,
  storageKey = STORAGE_KEY_DEFAULT,
}: AuthProviderProps) {
  // Initialize from sessionStorage
  const [apiKey, setApiKey] = useState<string | null>(() => {
    return sessionStorage.getItem(storageKey)
  })

  // Sync API client when apiKey changes
  const isAuthenticated = apiKey !== null

  // Update API client when we have a key
  if (apiKey) {
    apiClient.setApiKey(apiKey)
  }

  const login = useCallback(
    (newApiKey: string) => {
      sessionStorage.setItem(storageKey, newApiKey)
      apiClient.setApiKey(newApiKey)
      setApiKey(newApiKey)
    },
    [storageKey]
  )

  const logout = useCallback(() => {
    sessionStorage.removeItem(storageKey)
    apiClient.setApiKey('')
    setApiKey(null)
  }, [storageKey])

  const value = useMemo(
    () => ({
      isAuthenticated,
      apiKey,
      login,
      logout,
    }),
    [isAuthenticated, apiKey, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)

  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}
