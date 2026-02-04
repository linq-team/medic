/**
 * Tests for ServiceEditModal component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { ServiceEditModal, type ServiceEditModalProps } from './service-edit-modal'
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

// Import toast after mocking
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
  runbook: 'https://example.com/runbook',
  date_added: '2026-01-01T00:00:00Z',
  date_modified: null,
  date_muted: null,
}

// Helper to render the modal
function renderModal(
  props: Partial<ServiceEditModalProps> = {},
  queryClient?: QueryClient
) {
  const qc = queryClient ?? createTestQueryClient()
  const defaultProps: ServiceEditModalProps = {
    service: mockService,
    open: true,
    onOpenChange: vi.fn(),
    ...props,
  }

  const Wrapper = createWrapper(qc)
  return {
    ...render(
      <Wrapper>
        <ServiceEditModal {...defaultProps} />
      </Wrapper>
    ),
    queryClient: qc,
    props: defaultProps,
  }
}

describe('ServiceEditModal', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  describe('rendering', () => {
    it('renders the modal with title and description', () => {
      renderModal()

      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('Edit Service')).toBeInTheDocument()
      expect(screen.getByText(/Update the settings for Test Service/)).toBeInTheDocument()
    })

    it('renders all form fields', () => {
      renderModal()

      expect(screen.getByLabelText(/Service Name/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Team/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Priority/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Alert Interval/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Threshold/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Runbook URL/)).toBeInTheDocument()
    })

    it('pre-populates form with service data', () => {
      renderModal()

      expect(screen.getByDisplayValue('Test Service')).toBeInTheDocument()
      expect(screen.getByDisplayValue('platform')).toBeInTheDocument()
      expect(screen.getByDisplayValue('5')).toBeInTheDocument()
      expect(screen.getByDisplayValue('1')).toBeInTheDocument()
      expect(screen.getByDisplayValue('https://example.com/runbook')).toBeInTheDocument()
    })

    it('renders cancel and save buttons', () => {
      renderModal()

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Save Changes/i })).toBeInTheDocument()
    })

    it('disables save button when no changes made', () => {
      renderModal()

      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      expect(saveButton).toBeDisabled()
    })
  })

  describe('validation', () => {
    it('shows error when service name is empty', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Service Name/)
      await user.clear(input)
      // Trigger blur to mark as touched
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.getByText('Service name is required')).toBeInTheDocument()
      })
    })

    it('shows error for invalid alert interval', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Alert Interval/)
      await user.clear(input)
      await user.type(input, '0')
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.getByText('Alert interval must be at least 1 minute')).toBeInTheDocument()
      })
    })

    it('shows error for invalid threshold', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Threshold/)
      await user.clear(input)
      await user.type(input, '0')
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.getByText('Threshold must be at least 1')).toBeInTheDocument()
      })
    })

    it('shows error for invalid runbook URL', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Runbook URL/)
      await user.clear(input)
      await user.type(input, 'not-a-url')
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.getByText('Runbook must be a valid URL')).toBeInTheDocument()
      })
    })

    it('clears runbook error when valid URL is entered', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Runbook URL/)
      await user.clear(input)
      await user.type(input, 'not-a-url')
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.getByText('Runbook must be a valid URL')).toBeInTheDocument()
      })

      await user.clear(input)
      await user.type(input, 'https://valid-url.com')

      await waitFor(() => {
        expect(screen.queryByText('Runbook must be a valid URL')).not.toBeInTheDocument()
      })
    })
  })

  describe('form submission', () => {
    it('enables save button when form is valid and has changes', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Service Name/)
      await user.clear(input)
      await user.type(input, 'Updated Service Name')

      await waitFor(() => {
        const saveButton = screen.getByRole('button', { name: /Save Changes/i })
        expect(saveButton).not.toBeDisabled()
      })
    })

    it('calls updateService with correct payload on submit', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

      renderModal({}, queryClient)

      const input = screen.getByLabelText(/Service Name/)
      await user.clear(input)
      await user.type(input, 'Updated Service Name')

      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', {
          service_name: 'Updated Service Name',
        })
      })
    })

    it('shows success toast and closes modal on successful save', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

      const onOpenChange = vi.fn()
      renderModal({ onOpenChange }, queryClient)

      const input = screen.getByLabelText(/Service Name/)
      await user.clear(input)
      await user.type(input, 'Updated Service Name')

      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith(
          'Service updated',
          expect.objectContaining({
            description: expect.stringContaining('Test Service'),
          })
        )
        expect(onOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it('shows error toast on failed save', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockRejectedValueOnce(new Error('Update failed'))

      renderModal({}, queryClient)

      const input = screen.getByLabelText(/Service Name/)
      await user.clear(input)
      await user.type(input, 'Updated Service Name')

      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Failed to update service',
          expect.objectContaining({
            description: 'Update failed',
          })
        )
      })
    })

    it('shows loading state during save', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      // Create a promise that we can control
      let resolvePromise: (value: unknown) => void
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve
      })
      mockUpdateService.mockReturnValueOnce(pendingPromise as never)

      renderModal({}, queryClient)

      const input = screen.getByLabelText(/Service Name/)
      await user.clear(input)
      await user.type(input, 'Updated Service Name')

      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Saving/i })).toBeInTheDocument()
      })

      // Resolve the promise to clean up
      resolvePromise!({ success: true, message: 'Updated', results: '' })
    })

    it('sends only changed fields in update payload', async () => {
      const user = userEvent.setup()
      const mockUpdateService = vi.mocked(apiClient.updateService)
      mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

      renderModal({}, queryClient)

      // Change service name
      const nameInput = screen.getByLabelText(/Service Name/)
      await user.clear(nameInput)
      await user.type(nameInput, 'Updated Service Name')

      // Change team
      const teamInput = screen.getByLabelText(/Team/)
      await user.clear(teamInput)
      await user.type(teamInput, 'new-team')

      const saveButton = screen.getByRole('button', { name: /Save Changes/i })
      await user.click(saveButton)

      await waitFor(() => {
        expect(mockUpdateService).toHaveBeenCalledWith('test-service', {
          service_name: 'Updated Service Name',
          team: 'new-team',
        })
      })
    })
  })

  describe('modal behavior', () => {
    it('calls onOpenChange when cancel is clicked', async () => {
      const user = userEvent.setup()
      const onOpenChange = vi.fn()
      renderModal({ onOpenChange })

      const cancelButton = screen.getByRole('button', { name: /Cancel/i })
      await user.click(cancelButton)

      expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it('resets form when modal reopens', async () => {
      const { rerender, props, queryClient: qc } = renderModal({ open: false })

      // Open the modal
      const Wrapper = createWrapper(qc)
      rerender(
        <Wrapper>
          <ServiceEditModal {...props} open={true} />
        </Wrapper>
      )

      await waitFor(() => {
        expect(screen.getByDisplayValue('Test Service')).toBeInTheDocument()
      })
    })

    it('handles service with null values', () => {
      const serviceWithNulls: Service = {
        ...mockService,
        team: '',
        runbook: null,
      }

      renderModal({ service: serviceWithNulls })

      const teamInput = screen.getByLabelText(/Team/) as HTMLInputElement
      expect(teamInput.value).toBe('')

      const runbookInput = screen.getByLabelText(/Runbook URL/) as HTMLInputElement
      expect(runbookInput.value).toBe('')
    })
  })
})
