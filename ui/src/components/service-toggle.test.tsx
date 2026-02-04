/**
 * Tests for Service Toggle Components
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { MuteToggle, ActiveToggle } from './service-toggle'
import { apiClient, type Service } from '@/lib/api'

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

// Wrapper component with QueryClientProvider
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

// Mock service data
const mockService: Service = {
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

const mockMutedService: Service = {
  ...mockService,
  muted: 1,
}

const mockInactiveService: Service = {
  ...mockService,
  active: 0,
}

describe('MuteToggle', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('renders switch in unchecked state for unmuted service', () => {
    render(<MuteToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    expect(switchElement).toBeInTheDocument()
    expect(switchElement).not.toBeChecked()
    expect(switchElement).toHaveAttribute('aria-label', 'Mute Test Service')
  })

  it('renders switch in checked state for muted service', () => {
    render(<MuteToggle service={mockMutedService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    expect(switchElement).toBeChecked()
    expect(switchElement).toHaveAttribute('aria-label', 'Unmute Test Service')
  })

  it('calls updateService when toggling mute on', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    render(<MuteToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    await waitFor(() => {
      expect(mockUpdateService).toHaveBeenCalledWith('test-service', { muted: 1 })
    })

    expect(toast.success).toHaveBeenCalledWith('Test Service muted - alerts silenced')
  })

  it('calls updateService when toggling mute off', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    render(<MuteToggle service={mockMutedService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    await waitFor(() => {
      expect(mockUpdateService).toHaveBeenCalledWith('test-service', { muted: 0 })
    })

    expect(toast.success).toHaveBeenCalledWith('Test Service unmuted - alerts enabled')
  })

  it('shows error toast on failure', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockRejectedValueOnce(new Error('Network error'))

    render(<MuteToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to update Test Service: Network error')
    })
  })
})

describe('ActiveToggle', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('renders switch in checked state for active service', () => {
    render(<ActiveToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    expect(switchElement).toBeInTheDocument()
    expect(switchElement).toBeChecked()
    expect(switchElement).toHaveAttribute('aria-label', 'Deactivate Test Service')
  })

  it('renders switch in unchecked state for inactive service', () => {
    render(<ActiveToggle service={mockInactiveService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    expect(switchElement).not.toBeChecked()
    expect(switchElement).toHaveAttribute('aria-label', 'Activate Test Service')
  })

  it('activates service without confirmation dialog', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    render(<ActiveToggle service={mockInactiveService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    // Should not show dialog for activation
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await waitFor(() => {
      expect(mockUpdateService).toHaveBeenCalledWith('test-service', { active: 1 })
    })

    expect(toast.success).toHaveBeenCalledWith('Test Service activated - monitoring resumed')
  })

  it('shows confirmation dialog when deactivating', async () => {
    const user = userEvent.setup()

    render(<ActiveToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    // Dialog should appear
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    expect(screen.getByText('Deactivate Service')).toBeInTheDocument()
    expect(screen.getByText(/Are you sure you want to deactivate/)).toBeInTheDocument()
    expect(screen.getByText('Test Service', { exact: false })).toBeInTheDocument()
  })

  it('deactivates service after confirmation', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    render(<ActiveToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    // Open dialog
    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    // Confirm deactivation
    const confirmButton = screen.getByRole('button', { name: /deactivate/i })
    await user.click(confirmButton)

    await waitFor(() => {
      expect(mockUpdateService).toHaveBeenCalledWith('test-service', { active: 0 })
    })

    expect(toast.success).toHaveBeenCalledWith('Test Service deactivated - monitoring paused')
  })

  it('cancels deactivation when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)

    render(<ActiveToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    // Open dialog
    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: /cancel/i })
    await user.click(cancelButton)

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    // API should not be called
    expect(mockUpdateService).not.toHaveBeenCalled()
  })

  it('closes dialog on successful deactivation', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    render(<ActiveToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    // Open dialog
    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    // Confirm deactivation
    const confirmButton = screen.getByRole('button', { name: /deactivate/i })
    await user.click(confirmButton)

    // Dialog should close after success
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('shows error toast on deactivation failure', async () => {
    const user = userEvent.setup()
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockRejectedValueOnce(new Error('Server error'))

    render(<ActiveToggle service={mockService} />, {
      wrapper: createWrapper(queryClient),
    })

    // Open dialog
    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    // Confirm deactivation
    const confirmButton = screen.getByRole('button', { name: /deactivate/i })
    await user.click(confirmButton)

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to update Test Service: Server error')
    })
  })
})
