/**
 * Tests for snapshot hooks
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { useSnapshots, useSnapshot, useRestoreSnapshot, snapshotsKeys } from './use-snapshots'
import { servicesKeys } from './use-services'
import { apiClient, type Snapshot, type ApiResponse, type PaginatedResponse } from '@/lib/api'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      getSnapshots: vi.fn(),
      getSnapshotById: vi.fn(),
      restoreSnapshot: vi.fn(),
    },
  }
})

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
  snapshot_id: 1,
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
  action_type: 'edit',
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
    limit: 50,
    offset: 0,
    has_more: false,
  },
}

const mockSingleSnapshotResponse: ApiResponse<Snapshot> = {
  success: true,
  message: '',
  results: mockSnapshot,
}

describe('snapshotsKeys', () => {
  it('creates consistent query keys', () => {
    expect(snapshotsKeys.all).toEqual(['snapshots'])
    expect(snapshotsKeys.lists()).toEqual(['snapshots', 'list'])
    expect(snapshotsKeys.list({ service_id: 42 })).toEqual(['snapshots', 'list', { service_id: 42 }])
    expect(snapshotsKeys.details()).toEqual(['snapshots', 'detail'])
    expect(snapshotsKeys.detail(123)).toEqual(['snapshots', 'detail', 123])
  })
})

describe('useSnapshots', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('fetches snapshots without filters', async () => {
    const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
    mockGetSnapshots.mockResolvedValueOnce(mockSnapshotResponse)

    const { result } = renderHook(() => useSnapshots(), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetSnapshots).toHaveBeenCalledWith(undefined)
    expect(result.current.data).toEqual(mockSnapshotResponse)
  })

  it('fetches snapshots with service_id filter', async () => {
    const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
    mockGetSnapshots.mockResolvedValueOnce(mockSnapshotResponse)

    const { result } = renderHook(() => useSnapshots({ service_id: 42 }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetSnapshots).toHaveBeenCalledWith({ service_id: 42 })
  })

  it('fetches snapshots with action_type filter', async () => {
    const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
    mockGetSnapshots.mockResolvedValueOnce(mockSnapshotResponse)

    const { result } = renderHook(() => useSnapshots({ action_type: 'deactivate' }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetSnapshots).toHaveBeenCalledWith({ action_type: 'deactivate' })
  })

  it('fetches snapshots with date range filters', async () => {
    const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
    mockGetSnapshots.mockResolvedValueOnce(mockSnapshotResponse)

    const { result } = renderHook(
      () =>
        useSnapshots({
          start_date: '2026-01-01T00:00:00Z',
          end_date: '2026-01-31T23:59:59Z',
        }),
      {
        wrapper: createWrapper(queryClient),
      }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetSnapshots).toHaveBeenCalledWith({
      start_date: '2026-01-01T00:00:00Z',
      end_date: '2026-01-31T23:59:59Z',
    })
  })

  it('fetches snapshots with pagination', async () => {
    const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
    mockGetSnapshots.mockResolvedValueOnce({
      ...mockSnapshotResponse,
      results: {
        ...mockSnapshotResponse.results,
        limit: 20,
        offset: 40,
        has_more: true,
      },
    })

    const { result } = renderHook(() => useSnapshots({ limit: 20, offset: 40 }), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetSnapshots).toHaveBeenCalledWith({ limit: 20, offset: 40 })
    expect(result.current.data?.results.has_more).toBe(true)
  })

  it('handles error response', async () => {
    const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
    mockGetSnapshots.mockRejectedValueOnce(new Error('Failed to fetch snapshots'))

    const { result } = renderHook(() => useSnapshots(), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error?.message).toBe('Failed to fetch snapshots')
  })
})

describe('useSnapshot', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('fetches a single snapshot by ID', async () => {
    const mockGetSnapshotById = vi.mocked(apiClient.getSnapshotById)
    mockGetSnapshotById.mockResolvedValueOnce(mockSingleSnapshotResponse)

    const { result } = renderHook(() => useSnapshot(123), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetSnapshotById).toHaveBeenCalledWith(123)
    expect(result.current.data?.results).toEqual(mockSnapshot)
  })

  it('does not fetch when snapshotId is 0 (falsy)', async () => {
    const mockGetSnapshotById = vi.mocked(apiClient.getSnapshotById)

    const { result } = renderHook(() => useSnapshot(0), {
      wrapper: createWrapper(queryClient),
    })

    // Should remain in pending state since query is disabled
    expect(result.current.isPending).toBe(true)
    expect(result.current.fetchStatus).toBe('idle')
    expect(mockGetSnapshotById).not.toHaveBeenCalled()
  })

  it('handles error response', async () => {
    const mockGetSnapshotById = vi.mocked(apiClient.getSnapshotById)
    mockGetSnapshotById.mockRejectedValueOnce(new Error('Snapshot not found'))

    const { result } = renderHook(() => useSnapshot(999), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error?.message).toBe('Snapshot not found')
  })
})

describe('useRestoreSnapshot', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('calls apiClient.restoreSnapshot with correct parameters', async () => {
    const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
    const restoredSnapshot = {
      ...mockSnapshot,
      restored_at: '2026-01-20T12:00:00Z',
    }
    mockRestoreSnapshot.mockResolvedValueOnce({
      success: true,
      message: 'Snapshot restored',
      results: restoredSnapshot,
    })

    const { result } = renderHook(() => useRestoreSnapshot(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({ snapshotId: 123 })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockRestoreSnapshot).toHaveBeenCalledWith(123, undefined)
  })

  it('calls apiClient.restoreSnapshot with actor when provided', async () => {
    const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
    const restoredSnapshot = {
      ...mockSnapshot,
      restored_at: '2026-01-20T12:00:00Z',
    }
    mockRestoreSnapshot.mockResolvedValueOnce({
      success: true,
      message: 'Snapshot restored',
      results: restoredSnapshot,
    })

    const { result } = renderHook(() => useRestoreSnapshot(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({ snapshotId: 123, actor: 'admin@example.com' })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockRestoreSnapshot).toHaveBeenCalledWith(123, { actor: 'admin@example.com' })
  })

  it('invalidates snapshot queries on success', async () => {
    const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
    mockRestoreSnapshot.mockResolvedValueOnce({
      success: true,
      message: 'Snapshot restored',
      results: { ...mockSnapshot, restored_at: '2026-01-20T12:00:00Z' },
    })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useRestoreSnapshot(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({ snapshotId: 123 })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: snapshotsKeys.all })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: snapshotsKeys.detail(123) })
  })

  it('invalidates services queries on success', async () => {
    const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
    mockRestoreSnapshot.mockResolvedValueOnce({
      success: true,
      message: 'Snapshot restored',
      results: { ...mockSnapshot, restored_at: '2026-01-20T12:00:00Z' },
    })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useRestoreSnapshot(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({ snapshotId: 123 })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: servicesKeys.all })
  })

  it('handles error response', async () => {
    const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
    mockRestoreSnapshot.mockRejectedValueOnce(new Error('Snapshot already restored'))

    const { result } = renderHook(() => useRestoreSnapshot(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({ snapshotId: 123 })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error?.message).toBe('Snapshot already restored')
  })

  it('does not invalidate queries on error', async () => {
    const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
    mockRestoreSnapshot.mockRejectedValueOnce(new Error('Restore failed'))

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useRestoreSnapshot(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({ snapshotId: 123 })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    // Should not have been called since onSuccess didn't run
    expect(invalidateSpy).not.toHaveBeenCalled()
  })

  it('returns restored snapshot data on success', async () => {
    const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
    const restoredSnapshot = {
      ...mockSnapshot,
      restored_at: '2026-01-20T12:00:00Z',
    }
    mockRestoreSnapshot.mockResolvedValueOnce({
      success: true,
      message: 'Snapshot restored',
      results: restoredSnapshot,
    })

    const { result } = renderHook(() => useRestoreSnapshot(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({ snapshotId: 123 })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.results.restored_at).toBe('2026-01-20T12:00:00Z')
  })
})
