/**
 * Tests for useUndoToast hook
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { toast } from 'sonner'
import { useUndoToast } from './use-undo-toast'
import { apiClient, type Snapshot, type ApiResponse, type PaginatedResponse } from '@/lib/api'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      getSnapshots: vi.fn(),
      restoreSnapshot: vi.fn(),
    },
  }
})

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(() => 'toast-id-1'),
    error: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(() => 'loading-toast-id'),
    dismiss: vi.fn(),
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

// Wrapper component with QueryClientProvider
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

// Mock snapshot data
const mockSnapshot: Snapshot = {
  snapshot_id: 123,
  service_id: 42,
  snapshot_data: {
    service_id: 42,
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
  },
  action_type: 'deactivate',
  actor: 'user@example.com',
  created_at: '2026-01-15T10:00:00Z',
  restored_at: null,
}

const mockSnapshotResponse: ApiResponse<PaginatedResponse<Snapshot>> = {
  success: true,
  message: '',
  results: {
    entries: [mockSnapshot],
    total_count: 1,
    limit: 1,
    offset: 0,
    has_more: false,
  },
}

describe('useUndoToast', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  describe('showUndoToast', () => {
    it('fetches snapshot and shows toast with undo button', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce(mockSnapshotResponse)

      const { result } = renderHook(() => useUndoToast(), {
        wrapper: createWrapper(queryClient),
      })

      await act(async () => {
        result.current.showUndoToast({
          serviceId: 42,
          serviceName: 'Test Service',
          successMessage: 'Service deactivated',
          description: 'Monitoring paused',
        })
      })

      await waitFor(() => {
        expect(mockGetSnapshots).toHaveBeenCalledWith({ service_id: 42, limit: 1 })
      })

      expect(toast.success).toHaveBeenCalledWith(
        'Service deactivated',
        expect.objectContaining({
          description: 'Monitoring paused',
          duration: 10000,
          action: expect.objectContaining({
            label: 'Undo',
            onClick: expect.any(Function),
          }),
        })
      )
    })

    it('shows toast without undo button when no snapshot found', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: '',
        results: {
          entries: [],
          total_count: 0,
          limit: 1,
          offset: 0,
          has_more: false,
        },
      })

      const { result } = renderHook(() => useUndoToast(), {
        wrapper: createWrapper(queryClient),
      })

      await act(async () => {
        result.current.showUndoToast({
          serviceId: 42,
          serviceName: 'Test Service',
          successMessage: 'Service deactivated',
        })
      })

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('Service deactivated', { description: undefined })
      })
    })

    it('shows toast without undo button when snapshot fetch fails', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() => useUndoToast(), {
        wrapper: createWrapper(queryClient),
      })

      await act(async () => {
        result.current.showUndoToast({
          serviceId: 42,
          serviceName: 'Test Service',
          successMessage: 'Service deactivated',
          description: 'Monitoring paused',
        })
      })

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('Service deactivated', {
          description: 'Monitoring paused',
        })
      })
    })

    it('returns isRestoring as false initially', () => {
      const { result } = renderHook(() => useUndoToast(), {
        wrapper: createWrapper(queryClient),
      })

      expect(result.current.isRestoring).toBe(false)
    })
  })

  describe('showBulkUndoToast', () => {
    it('fetches snapshots for all services and shows bulk undo toast', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      // Return different snapshots for each service
      mockGetSnapshots
        .mockResolvedValueOnce({
          success: true,
          message: '',
          results: {
            entries: [{ ...mockSnapshot, snapshot_id: 101 }],
            total_count: 1,
            limit: 1,
            offset: 0,
            has_more: false,
          },
        })
        .mockResolvedValueOnce({
          success: true,
          message: '',
          results: {
            entries: [{ ...mockSnapshot, snapshot_id: 102, service_id: 43 }],
            total_count: 1,
            limit: 1,
            offset: 0,
            has_more: false,
          },
        })

      const { result } = renderHook(() => useUndoToast(), {
        wrapper: createWrapper(queryClient),
      })

      await act(async () => {
        result.current.showBulkUndoToast({
          services: [
            { serviceId: 42, serviceName: 'Service 1' },
            { serviceId: 43, serviceName: 'Service 2' },
          ],
          successMessage: '2 services deactivated',
        })
      })

      await waitFor(() => {
        expect(mockGetSnapshots).toHaveBeenCalledTimes(2)
      })

      expect(toast.success).toHaveBeenCalledWith(
        '2 services deactivated',
        expect.objectContaining({
          duration: 10000,
          action: expect.objectContaining({
            label: 'Undo',
            onClick: expect.any(Function),
          }),
        })
      )
    })

    it('shows toast without undo when no snapshots found for any service', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: '',
        results: {
          entries: [],
          total_count: 0,
          limit: 1,
          offset: 0,
          has_more: false,
        },
      })

      const { result } = renderHook(() => useUndoToast(), {
        wrapper: createWrapper(queryClient),
      })

      await act(async () => {
        result.current.showBulkUndoToast({
          services: [
            { serviceId: 42, serviceName: 'Service 1' },
            { serviceId: 43, serviceName: 'Service 2' },
          ],
          successMessage: '2 services deactivated',
        })
      })

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('2 services deactivated', { description: undefined })
      })
    })

    it('handles partial snapshot fetch failures gracefully', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)

      // First service succeeds, second fails
      mockGetSnapshots
        .mockResolvedValueOnce(mockSnapshotResponse)
        .mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() => useUndoToast(), {
        wrapper: createWrapper(queryClient),
      })

      await act(async () => {
        result.current.showBulkUndoToast({
          services: [
            { serviceId: 42, serviceName: 'Service 1' },
            { serviceId: 43, serviceName: 'Service 2' },
          ],
          successMessage: '2 services deactivated',
        })
      })

      await waitFor(() => {
        // Should still show undo toast with the one snapshot we got
        expect(toast.success).toHaveBeenCalledWith(
          '2 services deactivated',
          expect.objectContaining({
            action: expect.objectContaining({ label: 'Undo' }),
          })
        )
      })
    })
  })
})
