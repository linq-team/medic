/**
 * Tests for ServiceRowActions Component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { type ReactNode } from 'react'
import { ServiceRowActions } from './service-row-actions'
import { apiClient, type Service } from '@/lib/api'

// Mock react-router-dom's useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      updateService: vi.fn(),
    },
  }
})

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { toast } from 'sonner'

// Create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

// Wrapper component with QueryClientProvider and BrowserRouter
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryClientProvider>
    )
  }
}

// Mock service data
const mockActiveService: Service = {
  service_id: 1,
  heartbeat_name: 'test-service',
  service_name: 'Test Service',
  active: 1,
  alert_interval: 5,
  threshold: 1,
  team: 'platform',
  priority: 'p3',
  muted: 0,
  down: 0,
  runbook: null,
  date_added: '2026-01-01T00:00:00Z',
  date_modified: null,
  date_muted: null,
}

const mockInactiveService: Service = {
  ...mockActiveService,
  active: 0,
}

const mockMutedService: Service = {
  ...mockActiveService,
  muted: 1,
}

describe('ServiceRowActions', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('renders trigger button with correct aria-label', () => {
    render(<ServiceRowActions service={mockActiveService} />, {
      wrapper: createWrapper(queryClient),
    })

    const button = screen.getByRole('button', { name: /actions for test service/i })
    expect(button).toBeInTheDocument()
  })

  it('opens dropdown menu when clicked', async () => {
    const user = userEvent.setup()

    render(<ServiceRowActions service={mockActiveService} />, {
      wrapper: createWrapper(queryClient),
    })

    await user.click(screen.getByRole('button', { name: /actions for/i }))

    expect(screen.getByRole('menuitem', { name: /view details/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /mute/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /deactivate/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /view history/i })).toBeInTheDocument()
  })

  describe('View Details', () => {
    it('navigates to service detail page', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /view details/i }))

      expect(mockNavigate).toHaveBeenCalledWith('/services/test-service')
    })

    it('encodes special characters in heartbeat name', async () => {
      const user = userEvent.setup()
      const serviceWithSpecialChars = {
        ...mockActiveService,
        heartbeat_name: 'test/service#special',
      }

      render(<ServiceRowActions service={serviceWithSpecialChars} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /view details/i }))

      expect(mockNavigate).toHaveBeenCalledWith('/services/test%2Fservice%23special')
    })
  })

  describe('Edit', () => {
    it('opens edit modal when clicked', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /edit/i }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })
      expect(screen.getByText('Edit Service')).toBeInTheDocument()
    })
  })

  describe('Mute/Unmute', () => {
    it('shows Mute option for unmuted service', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))

      expect(screen.getByRole('menuitem', { name: /^mute$/i })).toBeInTheDocument()
      expect(screen.queryByRole('menuitem', { name: /unmute/i })).not.toBeInTheDocument()
    })

    it('shows Unmute option for muted service', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockMutedService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))

      expect(screen.getByRole('menuitem', { name: /unmute/i })).toBeInTheDocument()
      expect(screen.queryByRole('menuitem', { name: /^mute$/i })).not.toBeInTheDocument()
    })

    it('mutes service when Mute is clicked', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /^mute$/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { muted: 1 })
      })
      expect(toast.success).toHaveBeenCalledWith(
        'Service muted - alerts silenced',
        { description: 'Test Service' }
      )
    })

    it('unmutes service when Unmute is clicked', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

      render(<ServiceRowActions service={mockMutedService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /unmute/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { muted: 0 })
      })
      expect(toast.success).toHaveBeenCalledWith(
        'Service unmuted - alerts enabled',
        { description: 'Test Service' }
      )
    })
  })

  describe('Activate/Deactivate', () => {
    it('shows Deactivate option for active service', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))

      expect(screen.getByRole('menuitem', { name: /deactivate/i })).toBeInTheDocument()
      expect(screen.queryByRole('menuitem', { name: /^activate$/i })).not.toBeInTheDocument()
    })

    it('shows Activate option for inactive service', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockInactiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))

      expect(screen.getByRole('menuitem', { name: /^activate$/i })).toBeInTheDocument()
      expect(screen.queryByRole('menuitem', { name: /deactivate/i })).not.toBeInTheDocument()
    })

    it('activates service directly without confirmation', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

      render(<ServiceRowActions service={mockInactiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /^activate$/i }))

      // No dialog should appear
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { active: 1 })
      })
      expect(toast.success).toHaveBeenCalledWith(
        'Service activated - monitoring resumed',
        { description: 'Test Service' }
      )
    })

    it('shows confirmation dialog when Deactivate is clicked', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /deactivate/i }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })
      expect(screen.getByText('Deactivate Service')).toBeInTheDocument()
      expect(screen.getByText(/are you sure you want to deactivate/i)).toBeInTheDocument()
    })

    it('deactivates service after confirmation', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /deactivate/i }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      const dialog = screen.getByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: /^deactivate$/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { active: 0 })
      })
      expect(toast.success).toHaveBeenCalledWith(
        'Service deactivated - monitoring paused',
        { description: 'Test Service' }
      )
    })

    it('cancels deactivation when Cancel is clicked', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /deactivate/i }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /cancel/i }))

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
      expect(mockUpdateService).not.toHaveBeenCalled()
    })

    it('styles Deactivate option as destructive', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))

      const deactivateItem = screen.getByRole('menuitem', { name: /deactivate/i })
      expect(deactivateItem).toHaveClass('text-destructive')
    })
  })

  describe('View History', () => {
    it('navigates to history page with service filter', async () => {
      const user = userEvent.setup()

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /view history/i }))

      expect(mockNavigate).toHaveBeenCalledWith('/history?service=test-service')
    })
  })

  describe('Error handling', () => {
    it('shows error toast when mute fails', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockRejectedValueOnce(new Error('Network error'))

      render(<ServiceRowActions service={mockActiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /^mute$/i }))

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Failed to update service',
          { description: 'Test Service: Network error' }
        )
      })
    })

    it('shows error toast when activate fails', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockRejectedValueOnce(new Error('Server error'))

      render(<ServiceRowActions service={mockInactiveService} />, {
        wrapper: createWrapper(queryClient),
      })

      await user.click(screen.getByRole('button', { name: /actions for/i }))
      await user.click(screen.getByRole('menuitem', { name: /^activate$/i }))

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Failed to activate service',
          { description: 'Test Service: Server error' }
        )
      })
    })
  })
})
