/**
 * React Query hook for fetching alerts from the Medic API
 *
 * This hook provides type-safe data fetching with automatic caching,
 * background refetching, and loading/error states.
 */

import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import { apiClient, type Alert, type ApiResponse, type ApiError } from '@/lib/api'

/**
 * Query key factory for alerts
 * Using a factory pattern allows for consistent cache key management
 */
export const alertsKeys = {
  all: ['alerts'] as const,
  lists: () => [...alertsKeys.all, 'list'] as const,
  list: (filters?: AlertFilters) => [...alertsKeys.lists(), filters] as const,
  details: () => [...alertsKeys.all, 'detail'] as const,
  detail: (id: number) => [...alertsKeys.details(), id] as const,
}

/**
 * Filters for the alerts query
 */
export interface AlertFilters {
  active?: number // 0 or 1
}

/**
 * Hook to fetch all alerts with optional filters
 *
 * @param filters - Optional filters for active status
 * @param options - Additional React Query options
 * @returns Query result with alerts data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useAlerts()
 *
 * // With filters
 * const { data } = useAlerts({ active: 1 })
 *
 * // Access the alerts array
 * const alerts = data?.results ?? []
 * ```
 */
export function useAlerts(
  filters?: AlertFilters,
  options?: Omit<UseQueryOptions<ApiResponse<Alert[]>, ApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: alertsKeys.list(filters),
    queryFn: () => apiClient.getAlerts(filters),
    ...options,
  })
}
