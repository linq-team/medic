/**
 * React Query hooks for fetching and restoring service snapshots
 *
 * These hooks provide type-safe data fetching with automatic caching,
 * background refetching, and loading/error states for snapshot operations.
 */

import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query'
import {
  apiClient,
  type ApiError,
  type ApiResponse,
  type PaginatedResponse,
  type Snapshot,
  type SnapshotActionType,
} from '@/lib/api'
import { servicesKeys } from './use-services'

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for snapshots
 * Using a factory pattern allows for consistent cache key management
 */
export const snapshotsKeys = {
  all: ['snapshots'] as const,
  lists: () => [...snapshotsKeys.all, 'list'] as const,
  list: (filters?: SnapshotFilters) => [...snapshotsKeys.lists(), filters] as const,
  details: () => [...snapshotsKeys.all, 'detail'] as const,
  detail: (snapshotId: number) => [...snapshotsKeys.details(), snapshotId] as const,
}

// ============================================================================
// Types
// ============================================================================

/**
 * Filters for the snapshots query
 */
export interface SnapshotFilters {
  service_id?: number
  action_type?: SnapshotActionType
  start_date?: string // ISO format
  end_date?: string // ISO format
  limit?: number
  offset?: number
}

// ============================================================================
// Query Hooks
// ============================================================================

/**
 * Hook to fetch snapshots with optional filters and pagination
 *
 * @param filters - Optional filters for service_id, action_type, date range, and pagination
 * @param options - Additional React Query options
 * @returns Query result with snapshots data, loading state, and error
 *
 * @example
 * ```tsx
 * // Fetch all snapshots
 * const { data, isLoading, error } = useSnapshots()
 *
 * // Fetch snapshots for a specific service
 * const { data } = useSnapshots({ service_id: 42 })
 *
 * // Fetch snapshots with pagination
 * const { data } = useSnapshots({ limit: 20, offset: 0 })
 *
 * // Access the snapshots array
 * const snapshots = data?.results?.entries ?? []
 * const totalCount = data?.results?.total_count ?? 0
 * ```
 */
export function useSnapshots(
  filters?: SnapshotFilters,
  options?: Omit<UseQueryOptions<ApiResponse<PaginatedResponse<Snapshot>>, ApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: snapshotsKeys.list(filters),
    queryFn: () => apiClient.getSnapshots(filters),
    ...options,
  })
}

/**
 * Hook to fetch a single snapshot by ID
 *
 * @param snapshotId - The snapshot ID to fetch
 * @param options - Additional React Query options
 * @returns Query result with snapshot data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useSnapshot(123)
 *
 * // Access the snapshot
 * const snapshot = data?.results
 * ```
 */
export function useSnapshot(
  snapshotId: number,
  options?: Omit<UseQueryOptions<ApiResponse<Snapshot>, ApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: snapshotsKeys.detail(snapshotId),
    queryFn: () => apiClient.getSnapshotById(snapshotId),
    enabled: !!snapshotId,
    ...options,
  })
}

// ============================================================================
// Mutation Hooks
// ============================================================================

/**
 * Input type for restoring a snapshot
 */
export interface RestoreSnapshotInput {
  snapshotId: number
  actor?: string
}

/**
 * Hook for restoring a service from a snapshot
 *
 * @returns Mutation object with mutate/mutateAsync functions
 *
 * @example
 * ```tsx
 * const { mutate, isPending } = useRestoreSnapshot()
 *
 * // Restore a snapshot
 * mutate({ snapshotId: 123 })
 *
 * // With callbacks
 * mutate(
 *   { snapshotId: 123, actor: 'user@example.com' },
 *   {
 *     onSuccess: () => toast.success('Service restored'),
 *     onError: (error) => toast.error(error.message)
 *   }
 * )
 * ```
 */
export function useRestoreSnapshot() {
  const queryClient = useQueryClient()

  return useMutation<ApiResponse<Snapshot>, ApiError, RestoreSnapshotInput>({
    mutationFn: async ({ snapshotId, actor }) => {
      return apiClient.restoreSnapshot(snapshotId, actor ? { actor } : undefined)
    },

    // On success, invalidate both snapshots and services queries
    // The restored service will have changed, and the snapshot will be marked as restored
    onSuccess: (_data, { snapshotId }) => {
      // Invalidate all snapshot queries to reflect the restored_at change
      queryClient.invalidateQueries({ queryKey: snapshotsKeys.all })
      // Invalidate the specific snapshot detail
      queryClient.invalidateQueries({ queryKey: snapshotsKeys.detail(snapshotId) })
      // Invalidate all services queries since the restored service data changed
      queryClient.invalidateQueries({ queryKey: servicesKeys.all })
    },
  })
}
