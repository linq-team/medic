/**
 * Tests for BulkActionsToolbar Component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { BulkActionsToolbar } from './bulk-actions-toolbar'
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
    warning: vi.fn(),
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
const mockServices: Service[] = [
  {
    service_id: 1,
    heartbeat_name: 'service-1',
    service_name: 'Service One',
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
  },
  {
    service_id: 2,
    heartbeat_name: 'service-2',
    service_name: 'Service Two',
    active: 1,
    alert_interval: 5,
    threshold: 1,
    team: 'platform',
    priority: 'p2',
    muted: 1,
    down: 0,
    runbook: null,
    date_added: '2026-01-01T00:00:00Z',
    date_modified: null,
    date_muted: null,
  },
  {
    service_id: 3,
    heartbeat_name: 'service-3',
    service_name: 'Service Three',
    active: 0,
    alert_interval: 5,
    threshold: 1,
    team: 'sre',
    priority: 'p1',
    muted: 0,
    down: 1,
    runbook: null,
    date_added: '2026-01-01T00:00:00Z',
    date_modified: null,
    date_muted: null,
  },
]

describe('BulkActionsToolbar', () => {
  let queryClient: QueryClient
  const mockClearSelection = vi.fn()

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('renders nothing when no services are selected', () => {
    const { container } = render(
      <BulkActionsToolbar
        selectedServices={[]}
        onClearSelection={mockClearSelection}
      />,
      { wrapper: createWrapper(queryClient) }
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('renders toolbar with selected count for single service', () => {
    render(
      <BulkActionsToolbar
        selectedServices={[mockServices[0]]}
        onClearSelection={mockClearSelection}
      />,
      { wrapper: createWrapper(queryClient) }
    )

    expect(screen.getByText('1 service selected')).toBeInTheDocument()
  })

  it('renders toolbar with selected count for multiple services', () => {
    render(
      <BulkActionsToolbar
        selectedServices={mockServices}
        onClearSelection={mockClearSelection}
      />,
      { wrapper: createWrapper(queryClient) }
    )

    expect(screen.getByText('3 services selected')).toBeInTheDocument()
  })

  it('renders all action buttons', () => {
    render(
      <BulkActionsToolbar
        selectedServices={mockServices}
        onClearSelection={mockClearSelection}
      />,
      { wrapper: createWrapper(queryClient) }
    )

    // Use exact text matching to distinguish Mute from Unmute
    expect(screen.getByRole('button', { name: /^Mute$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Unmute$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Activate$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Deactivate$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Change Priority/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Change Team/i })).toBeInTheDocument()
  })

  it('calls onClearSelection when clear button is clicked', async () => {
    const user = userEvent.setup()

    render(
      <BulkActionsToolbar
        selectedServices={mockServices}
        onClearSelection={mockClearSelection}
      />,
      { wrapper: createWrapper(queryClient) }
    )

    const clearButton = screen.getByRole('button', { name: /clear selection/i })
    await user.click(clearButton)

    expect(mockClearSelection).toHaveBeenCalled()
  })

  describe('Mute action', () => {
    it('opens confirmation dialog when Mute is clicked', async () => {
      const user = userEvent.setup()

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })
      expect(screen.getByText('Mute Services')).toBeInTheDocument()
      expect(screen.getByText(/Mute 3 services/)).toBeInTheDocument()
    })

    it('shows service list in dialog', async () => {
      const user = userEvent.setup()

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      expect(screen.getByText('Service One')).toBeInTheDocument()
      expect(screen.getByText('Service Two')).toBeInTheDocument()
      expect(screen.getByText('Service Three')).toBeInTheDocument()
    })

    it('mutes all services when confirmed', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledTimes(3)
      })

      expect(mockUpdateService).toHaveBeenCalledWith('service-1', { muted: 1 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-2', { muted: 1 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-3', { muted: 1 })

      expect(toast.success).toHaveBeenCalledWith('3 services muted')
      expect(mockClearSelection).toHaveBeenCalled()
    })

    it('closes dialog when Cancel is clicked', async () => {
      const user = userEvent.setup()

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /cancel/i }))

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })
  })

  describe('Unmute action', () => {
    it('unmutes all services when confirmed', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Unmute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledTimes(3)
      })

      expect(mockUpdateService).toHaveBeenCalledWith('service-1', { muted: 0 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-2', { muted: 0 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-3', { muted: 0 })

      expect(toast.success).toHaveBeenCalledWith('3 services unmuted')
    })
  })

  describe('Activate action', () => {
    it('activates all services when confirmed', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Activate$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledTimes(3)
      })

      expect(mockUpdateService).toHaveBeenCalledWith('service-1', { active: 1 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-2', { active: 1 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-3', { active: 1 })

      expect(toast.success).toHaveBeenCalledWith('3 services activated')
    })
  })

  describe('Deactivate action', () => {
    it('shows destructive styling for deactivation dialog', async () => {
      const user = userEvent.setup()

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Deactivate$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      const title = screen.getByText('Deactivate Services')
      expect(title).toHaveClass('text-destructive')
      expect(screen.getByText(/Deactivated services will stop monitoring/)).toBeInTheDocument()
    })

    it('deactivates all services when confirmed', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Deactivate$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledTimes(3)
      })

      expect(mockUpdateService).toHaveBeenCalledWith('service-1', { active: 0 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-2', { active: 0 })
      expect(mockUpdateService).toHaveBeenCalledWith('service-3', { active: 0 })

      expect(toast.success).toHaveBeenCalledWith('3 services deactivated')
    })
  })

  describe('Change Priority action', () => {
    it('shows priority selector in dialog', async () => {
      const user = userEvent.setup()

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /Change Priority/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      const dialog = screen.getByRole('dialog')
      expect(within(dialog).getByText('Change Priority')).toBeInTheDocument()
      expect(within(dialog).getByText('New Priority')).toBeInTheDocument()
      expect(within(dialog).getByRole('combobox')).toBeInTheDocument()
    })

    it('updates priority for all services with default value when confirmed', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /Change Priority/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Use default P3 priority (avoid flaky Select interaction)
      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledTimes(3)
      })

      expect(mockUpdateService).toHaveBeenCalledWith('service-1', { priority: 'p3' })
      expect(mockUpdateService).toHaveBeenCalledWith('service-2', { priority: 'p3' })
      expect(mockUpdateService).toHaveBeenCalledWith('service-3', { priority: 'p3' })

      expect(toast.success).toHaveBeenCalledWith('3 services priority updated to P3')
    })
  })

  describe('Change Team action', () => {
    it('shows team input in dialog', async () => {
      const user = userEvent.setup()

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /Change Team/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      const dialog = screen.getByRole('dialog')
      expect(within(dialog).getByText('Change Team')).toBeInTheDocument()
      expect(within(dialog).getByText('New Team')).toBeInTheDocument()
      expect(within(dialog).getByPlaceholderText(/enter team name/i)).toBeInTheDocument()
    })

    it('updates team for all services when confirmed', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /Change Team/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Enter new team name
      const teamInput = screen.getByPlaceholderText(/enter team name/i)
      await user.type(teamInput, 'newteam')

      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledTimes(3)
      })

      expect(mockUpdateService).toHaveBeenCalledWith('service-1', { team: 'newteam' })
      expect(mockUpdateService).toHaveBeenCalledWith('service-2', { team: 'newteam' })
      expect(mockUpdateService).toHaveBeenCalledWith('service-3', { team: 'newteam' })

      expect(toast.success).toHaveBeenCalledWith('3 services team updated to newteam')
    })

    it('clears team when empty value is submitted', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /Change Team/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Don't enter anything, just confirm
      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledTimes(3)
      })

      expect(mockUpdateService).toHaveBeenCalledWith('service-1', { team: '' })
      expect(toast.success).toHaveBeenCalledWith('3 services team cleared')
    })
  })

  describe('Error handling', () => {
    it('shows error toast when all updates fail', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockRejectedValue(new Error('Network error'))

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Failed to mute services',
          expect.objectContaining({ description: expect.any(String) })
        )
      })
    })

    it('shows warning toast when some updates fail', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)

      // First two succeed, third fails
      mockUpdateService
        .mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })
        .mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })
        .mockRejectedValueOnce(new Error('Network error'))

      render(
        <BulkActionsToolbar
          selectedServices={mockServices}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /confirm/i }))

      await waitFor(() => {
        expect(toast.warning).toHaveBeenCalledWith(
          'Mute: 2 succeeded, 1 failed',
          expect.objectContaining({ description: expect.stringContaining('service-3') })
        )
      })
    })
  })

  describe('Loading state', () => {
    it('shows processing button text during bulk operation', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)

      // Create a promise that doesn't resolve immediately
      let resolvePromise: (value: { success: boolean; message: string; results: string }) => void
      mockUpdateService.mockImplementation(() => {
        return new Promise((resolve) => {
          resolvePromise = resolve
        })
      })

      render(
        <BulkActionsToolbar
          selectedServices={[mockServices[0]]}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      const confirmButton = screen.getByRole('button', { name: /confirm/i })
      await user.click(confirmButton)

      // Button should change to show loading state
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /processing/i })).toBeInTheDocument()
      })

      // Resolve the promise to clean up
      resolvePromise!({ success: true, message: 'Updated', results: '' })
    })
  })

  describe('Single service', () => {
    it('uses singular grammar for single service', async () => {
      const user = userEvent.setup()

      render(
        <BulkActionsToolbar
          selectedServices={[mockServices[0]]}
          onClearSelection={mockClearSelection}
        />,
        { wrapper: createWrapper(queryClient) }
      )

      await user.click(screen.getByRole('button', { name: /^Mute$/ }))

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      expect(screen.getByText(/Mute 1 service\?/)).toBeInTheDocument()
    })
  })
})
