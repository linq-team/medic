import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './components/theme-provider'
import { AuthProvider } from './components/auth-provider'
import { SettingsProvider } from './components/settings-provider'
import { Toaster } from './components/ui/sonner'

/**
 * React Query client with sensible defaults for the Medic UI
 *
 * staleTime: 30 seconds - data considered fresh for 30s before refetching
 * gcTime: 5 minutes - unused data kept in cache for 5 minutes (formerly cacheTime)
 * retry: 1 - retry failed requests once before showing error
 * refetchOnWindowFocus: true - refetch when user returns to tab (helps with stale dashboards)
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds
      gcTime: 5 * 60 * 1000, // 5 minutes (formerly cacheTime)
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider defaultTheme="system" storageKey="medic-ui-theme">
          <SettingsProvider>
            <AuthProvider>
              <App />
              <Toaster />
            </AuthProvider>
          </SettingsProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
)
