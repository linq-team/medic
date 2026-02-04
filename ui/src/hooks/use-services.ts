/**
 * React Query hook for fetching services from the Medic API
 *
 * This hook provides type-safe data fetching with automatic caching,
 * background refetching, and loading/error states.
 */

import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import { apiClient, type Service, type ApiResponse, type ApiError } from '@/lib/api'

/**
 * Query key factory for services
 * Using a factory pattern allows for consistent cache key management
 */
export const servicesKeys = {
  all: ['services'] as const,
  lists: () => [...servicesKeys.all, 'list'] as const,
  list: (filters?: ServiceFilters) => [...servicesKeys.lists(), filters] as const,
  details: () => [...servicesKeys.all, 'detail'] as const,
  detail: (heartbeatName: string) => [...servicesKeys.details(), heartbeatName] as const,
}

/**
 * Filters for the services query
 */
export interface ServiceFilters {
  service_name?: string
  active?: number
}

/**
 * Hook to fetch all services with optional filters
 *
 * @param filters - Optional filters for service_name and active status
 * @param options - Additional React Query options
 * @returns Query result with services data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useServices()
 *
 * // With filters
 * const { data } = useServices({ active: 1 })
 *
 * // Access the services array
 * const services = data?.results ?? []
 * ```
 */
export function useServices(
  filters?: ServiceFilters,
  options?: Omit<UseQueryOptions<ApiResponse<Service[]>, ApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: servicesKeys.list(filters),
    queryFn: () => apiClient.getServices(filters),
    ...options,
  })
}

/**
 * Hook to fetch a single service by heartbeat name
 *
 * @param heartbeatName - The heartbeat name to fetch
 * @param options - Additional React Query options
 * @returns Query result with service data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useService('my-service-heartbeat')
 *
 * // Access the service (returns array, usually with single item)
 * const service = data?.results?.[0]
 * ```
 */
export function useService(
  heartbeatName: string,
  options?: Omit<UseQueryOptions<ApiResponse<Service[]>, ApiError>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: servicesKeys.detail(heartbeatName),
    queryFn: () => apiClient.getServiceByHeartbeatName(heartbeatName),
    enabled: !!heartbeatName,
    ...options,
  })
}
