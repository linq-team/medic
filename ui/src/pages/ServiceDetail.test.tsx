/**
 * Tests for ServiceDetail page - Edit button and Quick Action buttons functionality
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { type ReactNode } from 'react'
import { ServiceDetail } from './ServiceDetail'
import { apiClient, type Service, type Snapshot } from '@/lib/api'
import { toast } from 'sonner'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      getServiceByHeartbeatName: vi.fn(),
      updateService: vi.fn(),
      getSnapshots: vi.fn().mockResolvedValue({
        success: true,
        message: '',
        results: {
          entries: [{ snapshot_id: 1 }],
          total_count: 1,
          limit: 1,
          offset: 0,
          has_more: false,
        },
      }),
      restoreSnapshot: vi.fn().mockResolvedValue({ success: true }),
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

// Create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
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
  runbook: 'https://example.com/runbook',
  date_added: '2026-01-01T00:00:00Z',
  date_modified: null,
  date_muted: null,
}

// Wrapper component with providers
function createWrapper(queryClient: QueryClient, initialTab?: string) {
  const initialEntry = initialTab
    ? `/services/test-service?tab=${initialTab}`
    : '/services/test-service'
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/services/:id" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }
}

// Helper to render the page
function renderPage(queryClient?: QueryClient, initialTab?: string) {
  const qc = queryClient ?? createTestQueryClient()
  const Wrapper = createWrapper(qc, initialTab)
  return {
    ...render(
      <Wrapper>
        <ServiceDetail />
      </Wrapper>
    ),
    queryClient: qc,
  }
}

describe('ServiceDetail - Edit Button', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  describe('rendering', () => {
    it('renders Edit button next to Back button', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [mockService],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Back/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      })
    })

    it('Edit button has pencil icon', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [mockService],
      })

      renderPage(queryClient)

      await waitFor(() => {
        const editButton = screen.getByRole('button', { name: /Edit/i })
        expect(editButton).toBeInTheDocument()
        // The button should contain an SVG icon
        expect(editButton.querySelector('svg')).toBeInTheDocument()
      })
    })

    it('does not render Edit button when service not found', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Service not found')).toBeInTheDocument()
      })

      expect(screen.queryByRole('button', { name: /Edit/i })).not.toBeInTheDocument()
    })

    it('does not render Edit button during loading', () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      // Return a promise that never resolves to keep loading state
      mockGetService.mockReturnValue(new Promise(() => {}))

      renderPage(queryClient)

      // Edit button should not be visible during loading
      expect(screen.queryByRole('button', { name: /Edit/i })).not.toBeInTheDocument()
    })
  })

  describe('modal interaction', () => {
    it('opens ServiceEditModal when Edit button is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [mockService],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      })

      const editButton = screen.getByRole('button', { name: /Edit/i })
      await user.click(editButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
        expect(screen.getByText('Edit Service')).toBeInTheDocument()
      })
    })

    it('pre-populates modal with current service data', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [mockService],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      })

      const editButton = screen.getByRole('button', { name: /Edit/i })
      await user.click(editButton)

      await waitFor(() => {
        expect(screen.getByDisplayValue('Test Service')).toBeInTheDocument()
        expect(screen.getByDisplayValue('platform')).toBeInTheDocument()
        expect(screen.getByDisplayValue('5')).toBeInTheDocument()
        expect(screen.getByDisplayValue('1')).toBeInTheDocument()
        expect(screen.getByDisplayValue('https://example.com/runbook')).toBeInTheDocument()
      })
    })

    it('closes modal when Cancel is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [mockService],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      })

      // Open modal
      const editButton = screen.getByRole('button', { name: /Edit/i })
      await user.click(editButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Close modal via Cancel button
      const cancelButton = screen.getByRole('button', { name: /Cancel/i })
      await user.click(cancelButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('closes modal after successful edit', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      })

      // Open modal
      const editButton = screen.getByRole('button', { name: /Edit/i })
      await user.click(editButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Make a change
      const serviceNameInput = screen.getByLabelText(/Service Name/)
      await user.clear(serviceNameInput)
      await user.type(serviceNameInput, 'Updated Service Name')

      // Save
      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('refreshes page data after successful edit', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      const updatedService = {
        ...mockService,
        service_name: 'Updated Service Name',
      }

      // First call returns original service, subsequent calls return updated
      mockGetService
        .mockResolvedValueOnce({
          success: true,
          message: 'OK',
          results: [mockService],
        })
        .mockResolvedValue({
          success: true,
          message: 'OK',
          results: [updatedService],
        })

      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Test Service' })).toBeInTheDocument()
      })

      // Open modal
      const editButton = screen.getByRole('button', { name: /Edit/i })
      await user.click(editButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Make a change
      const serviceNameInput = screen.getByLabelText(/Service Name/)
      await user.clear(serviceNameInput)
      await user.type(serviceNameInput, 'Updated Service Name')

      // Save
      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      await user.click(saveButton)

      // Wait for modal to close and data to refresh
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })

      // The page should have refetched the data
      await waitFor(() => {
        // getService should have been called more than once (initial + refetch after update)
        expect(mockGetService).toHaveBeenCalledTimes(2)
      })
    })
  })
})

describe('ServiceDetail - Quick Action Buttons', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  describe('Mute/Unmute Button', () => {
    it('renders Mute button when service is not muted', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [{ ...mockService, muted: 0 }],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Mute/i })).toBeInTheDocument()
      })
    })

    it('renders Unmute button when service is muted', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [{ ...mockService, muted: 1 }],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Unmute/i })).toBeInTheDocument()
      })
    })

    it('calls updateService when Mute button is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, muted: 0 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Mute/i })).toBeInTheDocument()
      })

      const muteButton = screen.getByRole('button', { name: /Mute/i })
      await user.click(muteButton)

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { muted: 1 })
      })
    })

    it('calls updateService when Unmute button is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, muted: 1 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Unmute/i })).toBeInTheDocument()
      })

      const unmuteButton = screen.getByRole('button', { name: /Unmute/i })
      await user.click(unmuteButton)

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { muted: 0 })
      })
    })

    it('shows success toast with undo button when mute succeeds', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)
      const mockToastSuccess = vi.mocked(toast.success)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, muted: 0 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Mute/i })).toBeInTheDocument()
      })

      const muteButton = screen.getByRole('button', { name: /Mute/i })
      await user.click(muteButton)

      // Mute is a destructive action, so uses undo toast with action button
      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith(
          expect.stringContaining('muted'),
          expect.objectContaining({
            duration: 10000,
            action: expect.objectContaining({ label: 'Undo' }),
          })
        )
      })
    })

    it('shows error toast when mute fails', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)
      const mockToastError = vi.mocked(toast.error)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, muted: 0 }],
      })
      mockUpdateService.mockRejectedValueOnce(new Error('Network error'))

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Mute/i })).toBeInTheDocument()
      })

      const muteButton = screen.getByRole('button', { name: /Mute/i })
      await user.click(muteButton)

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith(
          expect.stringContaining('Failed')
        )
      })
    })
  })

  describe('Activate/Deactivate Button', () => {
    it('renders Deactivate button when service is active', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })
    })

    it('renders Activate button when service is inactive', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 0 }],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Activate/i })).toBeInTheDocument()
      })
    })

    it('shows confirmation dialog when Deactivate button is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)

      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })

      const deactivateButton = screen.getByRole('button', { name: /Deactivate/i })
      await user.click(deactivateButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
        expect(screen.getByText('Deactivate Service')).toBeInTheDocument()
        expect(screen.getByText(/Are you sure you want to deactivate/)).toBeInTheDocument()
      })
    })

    it('does not show confirmation dialog when Activate button is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 0 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Activate/i })).toBeInTheDocument()
      })

      const activateButton = screen.getByRole('button', { name: /Activate/i })
      await user.click(activateButton)

      // Should not show dialog
      expect(screen.queryByText('Deactivate Service')).not.toBeInTheDocument()

      // Should call updateService directly
      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { active: 1 })
      })
    })

    it('closes confirmation dialog when Cancel is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)

      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })

      // Open dialog
      const deactivateButton = screen.getByRole('button', { name: /Deactivate/i })
      await user.click(deactivateButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Get Cancel button inside dialog
      const dialog = screen.getByRole('dialog')
      const cancelButton = within(dialog).getByRole('button', { name: /Cancel/i })
      await user.click(cancelButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('calls updateService when Deactivate is confirmed', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })

      // Open dialog
      const deactivateButton = screen.getByRole('button', { name: /Deactivate/i })
      await user.click(deactivateButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm deactivation
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Deactivate$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', { active: 0 })
      })
    })

    it('shows success toast with undo button when deactivate succeeds', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)
      const mockToastSuccess = vi.mocked(toast.success)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })

      // Open dialog
      const deactivateButton = screen.getByRole('button', { name: /Deactivate/i })
      await user.click(deactivateButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm deactivation
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Deactivate$/i })
      await user.click(confirmButton)

      // Deactivate is a destructive action, so uses undo toast with action button
      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith(
          expect.stringContaining('deactivated'),
          expect.objectContaining({
            duration: 10000,
            action: expect.objectContaining({ label: 'Undo' }),
          })
        )
      })
    })

    it('shows success toast when activate succeeds', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)
      const mockToastSuccess = vi.mocked(toast.success)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 0 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Activate/i })).toBeInTheDocument()
      })

      const activateButton = screen.getByRole('button', { name: /Activate/i })
      await user.click(activateButton)

      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith(
          expect.stringContaining('activated')
        )
      })
    })

    it('shows error toast when deactivate fails', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)
      const mockToastError = vi.mocked(toast.error)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })
      mockUpdateService.mockRejectedValueOnce(new Error('Network error'))

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })

      // Open dialog
      const deactivateButton = screen.getByRole('button', { name: /Deactivate/i })
      await user.click(deactivateButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm deactivation
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Deactivate$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith(
          expect.stringContaining('Failed')
        )
      })
    })

    it('closes dialog after deactivate succeeds', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })
      mockUpdateService.mockResolvedValueOnce({
        success: true,
        message: 'Updated',
        results: '',
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })

      // Open dialog
      const deactivateButton = screen.getByRole('button', { name: /Deactivate/i })
      await user.click(deactivateButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm deactivation
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Deactivate$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('closes dialog after deactivate fails', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockUpdateService = vi.mocked(apiClient.updateService)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [{ ...mockService, active: 1 }],
      })
      mockUpdateService.mockRejectedValueOnce(new Error('Network error'))

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Deactivate/i })).toBeInTheDocument()
      })

      // Open dialog
      const deactivateButton = screen.getByRole('button', { name: /Deactivate/i })
      await user.click(deactivateButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm deactivation
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Deactivate$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })
  })

  describe('Button states', () => {
    it('does not render quick action buttons when service not found', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Service not found')).toBeInTheDocument()
      })

      expect(screen.queryByRole('button', { name: /Mute/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Unmute/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Activate/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Deactivate/i })).not.toBeInTheDocument()
    })

    it('does not render quick action buttons during loading', () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      // Return a promise that never resolves to keep loading state
      mockGetService.mockReturnValue(new Promise(() => {}))

      renderPage(queryClient)

      expect(screen.queryByRole('button', { name: /Mute/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Unmute/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Activate/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Deactivate/i })).not.toBeInTheDocument()
    })
  })
})

// Mock snapshot data
const mockSnapshot: Snapshot = {
  snapshot_id: 1,
  service_id: 1,
  snapshot_data: {
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
    runbook: 'https://example.com/runbook',
    date_added: '2026-01-01T00:00:00Z',
    date_modified: null,
    date_muted: null,
  },
  action_type: 'edit',
  actor: 'user@example.com',
  created_at: '2026-02-01T12:00:00Z',
  restored_at: null,
}

const mockRestoredSnapshot: Snapshot = {
  ...mockSnapshot,
  snapshot_id: 2,
  action_type: 'mute',
  created_at: '2026-01-15T12:00:00Z',
  restored_at: '2026-01-20T14:30:00Z',
}

describe('ServiceDetail - History Tab', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  describe('Tab Navigation', () => {
    it('renders Overview and History tabs', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [mockService],
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /Overview/i })).toBeInTheDocument()
        expect(screen.getByRole('tab', { name: /History/i })).toBeInTheDocument()
      })
    })

    it('shows Overview tab as active by default', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      mockGetService.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: [mockService],
      })

      renderPage(queryClient)

      await waitFor(() => {
        const overviewTab = screen.getByRole('tab', { name: /Overview/i })
        expect(overviewTab).toHaveAttribute('data-state', 'active')
      })
    })

    it('switches to History tab when clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /History/i })).toBeInTheDocument()
      })

      const historyTab = screen.getByRole('tab', { name: /History/i })
      await user.click(historyTab)

      await waitFor(() => {
        expect(historyTab).toHaveAttribute('data-state', 'active')
      })
    })
  })

  describe('History Tab Content', () => {
    it('shows empty state message when no snapshots exist', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByText('No history yet')).toBeInTheDocument()
        expect(
          screen.getByText(/Snapshots are created automatically when changes are made/)
        ).toBeInTheDocument()
      })
    })

    it('renders snapshot list with action type, actor, and date', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        // Check action type badge
        expect(screen.getByText('Edited')).toBeInTheDocument()
        // Check actor
        expect(screen.getByText('user@example.com')).toBeInTheDocument()
        // Check restore button exists
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })
    })

    it('shows Restored badge for already-restored snapshots', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockRestoredSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByText('Restored')).toBeInTheDocument()
        // Should not show Restore button for already-restored snapshot
        expect(screen.queryByRole('button', { name: /^Restore$/i })).not.toBeInTheDocument()
      })
    })

    it('shows loading skeleton while fetching snapshots', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      // Never resolve to keep loading state
      mockGetSnapshots.mockReturnValue(new Promise(() => {}))

      renderPage(queryClient, 'history')

      await waitFor(() => {
        // Check that skeleton elements are rendered
        expect(screen.getByText('Change History')).toBeInTheDocument()
      })
    })
  })

  describe('Restore Functionality', () => {
    it('opens restore confirmation dialog when Restore button is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
        expect(screen.getByText('Restore Service')).toBeInTheDocument()
        expect(screen.getByText(/Are you sure you want to restore/)).toBeInTheDocument()
      })
    })

    it('shows snapshot state preview in restore dialog', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByText('This will restore the following state:')).toBeInTheDocument()
        // Check that snapshot data is shown
        expect(screen.getByText('Service Name:')).toBeInTheDocument()
        expect(screen.getByText('Active:')).toBeInTheDocument()
        expect(screen.getByText('Muted:')).toBeInTheDocument()
        expect(screen.getByText('Priority:')).toBeInTheDocument()
      })
    })

    it('closes dialog when Cancel is clicked', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Close dialog
      const dialog = screen.getByRole('dialog')
      const cancelButton = within(dialog).getByRole('button', { name: /Cancel/i })
      await user.click(cancelButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('calls restoreSnapshot when Restore is confirmed', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockResolvedValueOnce({
        success: true,
        message: 'Restored',
        results: { ...mockSnapshot, restored_at: '2026-02-05T12:00:00Z' },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockRestoreSnapshot).toHaveBeenCalledWith(1, undefined)
      })
    })

    it('shows success toast when restore succeeds', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
      const mockToastSuccess = vi.mocked(toast.success)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockResolvedValueOnce({
        success: true,
        message: 'Restored',
        results: { ...mockSnapshot, restored_at: '2026-02-05T12:00:00Z' },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith(expect.stringContaining('restored'))
      })
    })

    it('shows error toast when restore fails', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
      const mockToastError = vi.mocked(toast.error)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockRejectedValueOnce(new Error('Restore failed'))

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith(expect.stringContaining('Failed'))
      })
    })

    it('closes dialog after restore succeeds', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockResolvedValueOnce({
        success: true,
        message: 'Restored',
        results: { ...mockSnapshot, restored_at: '2026-02-05T12:00:00Z' },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('closes dialog after restore fails', async () => {
      const user = userEvent.setup()
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockRejectedValueOnce(new Error('Restore failed'))

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })
  })

  describe('Action Type Display', () => {
    it('displays Muted for mute action type', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      const muteSnapshot: Snapshot = { ...mockSnapshot, action_type: 'mute' }

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [muteSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByText('Muted')).toBeInTheDocument()
      })
    })

    it('displays Deactivated for deactivate action type', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      const deactivateSnapshot: Snapshot = { ...mockSnapshot, action_type: 'deactivate' }

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [deactivateSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByText('Deactivated')).toBeInTheDocument()
      })
    })

    it('displays Priority Changed for priority_change action type', async () => {
      const mockGetService = vi.mocked(apiClient.getServiceByHeartbeatName)
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      const priorityChangeSnapshot: Snapshot = { ...mockSnapshot, action_type: 'priority_change' }

      mockGetService.mockResolvedValue({
        success: true,
        message: 'OK',
        results: [mockService],
      })
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [priorityChangeSnapshot],
          total_count: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, 'history')

      await waitFor(() => {
        expect(screen.getByText('Priority Changed')).toBeInTheDocument()
      })
    })
  })
})
