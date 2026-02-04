/**
 * Tests for ServiceCreateModal component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { ServiceCreateModal, type ServiceCreateModalProps } from './service-create-modal'
import { apiClient } from '@/lib/api'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      createService: vi.fn(),
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

// Helper to render the modal
function renderModal(
  props: Partial<ServiceCreateModalProps> = {},
  queryClient?: QueryClient
) {
  const qc = queryClient ?? createTestQueryClient()
  const defaultProps: ServiceCreateModalProps = {
    open: true,
    onOpenChange: vi.fn(),
    ...props,
  }

  const Wrapper = createWrapper(qc)
  return {
    ...render(
      <Wrapper>
        <ServiceCreateModal {...defaultProps} />
      </Wrapper>
    ),
    queryClient: qc,
    props: defaultProps,
  }
}

describe('ServiceCreateModal', () => {
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
      expect(screen.getByText('Add Service')).toBeInTheDocument()
      expect(screen.getByText(/Create a new service to monitor/)).toBeInTheDocument()
    })

    it('renders all form fields', () => {
      renderModal()

      expect(screen.getByLabelText(/Heartbeat Name/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Service Name/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Team/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Priority/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Alert Interval/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Threshold/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Runbook URL/)).toBeInTheDocument()
    })

    it('has sensible default values', () => {
      renderModal()

      // Priority defaults to P3
      expect(screen.getByRole('combobox')).toHaveTextContent('P3 - Normal')

      // Alert interval defaults to 5
      expect(screen.getByDisplayValue('5')).toBeInTheDocument()

      // Threshold defaults to 1
      expect(screen.getByDisplayValue('1')).toBeInTheDocument()
    })

    it('renders cancel and create buttons', () => {
      renderModal()

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Create Service/i })).toBeInTheDocument()
    })

    it('disables create button when required fields are empty', () => {
      renderModal()

      const createButton = screen.getByRole('button', { name: /Create Service/i })
      expect(createButton).toBeDisabled()
    })

    it('shows hint text for heartbeat name field', () => {
      renderModal()

      expect(screen.getByText(/Unique identifier used for API calls/)).toBeInTheDocument()
    })
  })

  describe('validation', () => {
    it('shows error when heartbeat name is empty', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Heartbeat Name/)
      await user.type(input, 'test')
      await user.clear(input)
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.getByText('Heartbeat name is required')).toBeInTheDocument()
      })
    })

    it('shows error when heartbeat name contains invalid characters', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Heartbeat Name/)
      await user.type(input, 'invalid name!')
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.getByText(/can only contain letters, numbers, hyphens, and underscores/)).toBeInTheDocument()
      })
    })

    it('accepts valid heartbeat name with hyphens and underscores', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Heartbeat Name/)
      await user.type(input, 'my-service_123')
      fireEvent.blur(input)

      await waitFor(() => {
        expect(screen.queryByText(/can only contain/)).not.toBeInTheDocument()
      })
    })

    it('shows error when service name is empty', async () => {
      const user = userEvent.setup()
      renderModal()

      const input = screen.getByLabelText(/Service Name/)
      await user.type(input, 'test')
      await user.clear(input)
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
    it('enables create button when form is valid', async () => {
      const user = userEvent.setup()
      renderModal()

      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      const serviceInput = screen.getByLabelText(/Service Name/)

      await user.type(heartbeatInput, 'my-service')
      await user.type(serviceInput, 'My Service')

      await waitFor(() => {
        const createButton = screen.getByRole('button', { name: /Create Service/i })
        expect(createButton).not.toBeDisabled()
      })
    })

    it('calls createService with correct payload on submit', async () => {
      const user = userEvent.setup()
      const mockCreateService = vi.mocked(apiClient.createService)
      mockCreateService.mockResolvedValueOnce({ success: true, message: 'Created', results: '' })

      renderModal({}, queryClient)

      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      const serviceInput = screen.getByLabelText(/Service Name/)
      const teamInput = screen.getByLabelText(/Team/)

      await user.type(heartbeatInput, 'my-service')
      await user.type(serviceInput, 'My Service')
      await user.type(teamInput, 'platform')

      const createButton = screen.getByRole('button', { name: /Create Service/i })
      await user.click(createButton)

      await waitFor(() => {
        expect(mockCreateService).toHaveBeenCalledWith({
          heartbeat_name: 'my-service',
          service_name: 'My Service',
          alert_interval: 5,
          threshold: 1,
          priority: 'p3',
          team: 'platform',
          runbook: undefined,
        })
      })
    })

    it('shows success toast and closes modal on successful create', async () => {
      const user = userEvent.setup()
      const mockCreateService = vi.mocked(apiClient.createService)
      mockCreateService.mockResolvedValueOnce({ success: true, message: 'Created', results: '' })

      const onOpenChange = vi.fn()
      renderModal({ onOpenChange }, queryClient)

      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      const serviceInput = screen.getByLabelText(/Service Name/)

      await user.type(heartbeatInput, 'my-service')
      await user.type(serviceInput, 'My Service')

      const createButton = screen.getByRole('button', { name: /Create Service/i })
      await user.click(createButton)

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith(
          'Service created',
          expect.objectContaining({
            description: expect.stringContaining('My Service'),
          })
        )
        expect(onOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it('shows error toast on failed create', async () => {
      const user = userEvent.setup()
      const mockCreateService = vi.mocked(apiClient.createService)
      mockCreateService.mockRejectedValueOnce(new Error('Create failed'))

      renderModal({}, queryClient)

      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      const serviceInput = screen.getByLabelText(/Service Name/)

      await user.type(heartbeatInput, 'my-service')
      await user.type(serviceInput, 'My Service')

      const createButton = screen.getByRole('button', { name: /Create Service/i })
      await user.click(createButton)

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Failed to create service',
          expect.objectContaining({
            description: 'Create failed',
          })
        )
      })
    })

    it('shows specific error for duplicate heartbeat name', async () => {
      const user = userEvent.setup()
      const mockCreateService = vi.mocked(apiClient.createService)
      mockCreateService.mockRejectedValueOnce(new Error('Service already exists'))

      renderModal({}, queryClient)

      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      const serviceInput = screen.getByLabelText(/Service Name/)

      await user.type(heartbeatInput, 'existing-service')
      await user.type(serviceInput, 'Existing Service')

      const createButton = screen.getByRole('button', { name: /Create Service/i })
      await user.click(createButton)

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Service already exists',
          expect.objectContaining({
            description: expect.stringContaining('existing-service'),
          })
        )
      })
    })

    it('shows loading state during create', async () => {
      const user = userEvent.setup()
      const mockCreateService = vi.mocked(apiClient.createService)
      // Create a promise that we can control
      let resolvePromise: (value: unknown) => void
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve
      })
      mockCreateService.mockReturnValueOnce(pendingPromise as never)

      renderModal({}, queryClient)

      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      const serviceInput = screen.getByLabelText(/Service Name/)

      await user.type(heartbeatInput, 'my-service')
      await user.type(serviceInput, 'My Service')

      const createButton = screen.getByRole('button', { name: /Create Service/i })
      await user.click(createButton)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Creating/i })).toBeInTheDocument()
      })

      // Resolve the promise to clean up
      resolvePromise!({ success: true, message: 'Created', results: '' })
    })

    it('omits optional empty fields from payload', async () => {
      const user = userEvent.setup()
      const mockCreateService = vi.mocked(apiClient.createService)
      mockCreateService.mockResolvedValueOnce({ success: true, message: 'Created', results: '' })

      renderModal({}, queryClient)

      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      const serviceInput = screen.getByLabelText(/Service Name/)

      await user.type(heartbeatInput, 'my-service')
      await user.type(serviceInput, 'My Service')
      // Leave team and runbook empty

      const createButton = screen.getByRole('button', { name: /Create Service/i })
      await user.click(createButton)

      await waitFor(() => {
        expect(mockCreateService).toHaveBeenCalledWith({
          heartbeat_name: 'my-service',
          service_name: 'My Service',
          alert_interval: 5,
          threshold: 1,
          priority: 'p3',
          team: undefined,
          runbook: undefined,
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
      const user = userEvent.setup()
      const { rerender, props, queryClient: qc } = renderModal({ open: true })

      // Type something in the form
      const heartbeatInput = screen.getByLabelText(/Heartbeat Name/)
      await user.type(heartbeatInput, 'test-service')

      expect(screen.getByDisplayValue('test-service')).toBeInTheDocument()

      // Close the modal
      const Wrapper = createWrapper(qc)
      rerender(
        <Wrapper>
          <ServiceCreateModal {...props} open={false} />
        </Wrapper>
      )

      // Reopen the modal
      rerender(
        <Wrapper>
          <ServiceCreateModal {...props} open={true} />
        </Wrapper>
      )

      // Form should be reset
      await waitFor(() => {
        const newHeartbeatInput = screen.getByLabelText(/Heartbeat Name/) as HTMLInputElement
        expect(newHeartbeatInput.value).toBe('')
      })
    })

    it('does not render when closed', () => {
      renderModal({ open: false })

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })
})
