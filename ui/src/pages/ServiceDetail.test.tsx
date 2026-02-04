/**
 * Tests for ServiceDetail page - Edit button functionality
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { type ReactNode } from 'react'
import { ServiceDetail } from './ServiceDetail'
import { apiClient, type Service } from '@/lib/api'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      getServiceByHeartbeatName: vi.fn(),
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
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/services/test-service']}>
          <Routes>
            <Route path="/services/:id" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }
}

// Helper to render the page
function renderPage(queryClient?: QueryClient) {
  const qc = queryClient ?? createTestQueryClient()
  const Wrapper = createWrapper(qc)
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
