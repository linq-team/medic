/**
 * React Query hook for fetching playbooks from the Medic API
 *
 * This hook provides type-safe data fetching with automatic caching,
 * background refetching, and loading/error states.
 */

import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import { apiClient, type Playbook, type ApiResponse, type ApiError } from '@/lib/api'

/**
 * Query key factory for playbooks
 * Using a factory pattern allows for consistent cache key management
 */
export const playbooksKeys = {
  all: ['playbooks'] as const,
  lists: () => [...playbooksKeys.all, 'list'] as const,
  list: (filters?: PlaybookFilters) => [...playbooksKeys.lists(), filters] as const,
}

/**
 * Filters for the playbooks query
 */
export interface PlaybookFilters {
  active?: number
  trigger_type?: string
}

/**
 * Hook to fetch all playbooks with optional filters
 *
 * @param filters - Optional filters for active status and trigger_type
 * @param options - Additional React Query options
 * @returns Query result with playbooks data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = usePlaybooks()
 *
 * // With filters
 * const { data } = usePlaybooks({ active: 1 })
 *
 * // Access the playbooks array
 * const playbooks = data?.results ?? []
 * ```
 */
export function usePlaybooks(
  filters?: PlaybookFilters,
  options?: Omit<UseQueryOptions<ApiResponse<Playbook[]>, ApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: playbooksKeys.list(filters),
    queryFn: () => apiClient.getPlaybooks(filters),
    ...options,
  })
}
