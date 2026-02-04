/**
 * React Query hook for fetching audit logs from the Medic API
 *
 * This hook provides type-safe data fetching with automatic caching,
 * background refetching, and loading/error states.
 */

import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import {
  apiClient,
  type AuditLogEntry,
  type AuditActionType,
  type ApiResponse,
  type ApiError,
  type PaginatedResponse,
} from '@/lib/api'

/**
 * Query key factory for audit logs
 * Using a factory pattern allows for consistent cache key management
 */
export const auditLogsKeys = {
  all: ['auditLogs'] as const,
  lists: () => [...auditLogsKeys.all, 'list'] as const,
  list: (filters?: AuditLogFilters) => [...auditLogsKeys.lists(), filters] as const,
}

/**
 * Filters for the audit logs query
 */
export interface AuditLogFilters {
  execution_id?: number
  service_id?: number
  action_type?: AuditActionType
  actor?: string
  start_date?: string // ISO format
  end_date?: string // ISO format
  limit?: number
  offset?: number
}

/**
 * Hook to fetch audit logs with optional filters and pagination
 *
 * @param filters - Optional filters for the audit logs query
 * @param options - Additional React Query options
 * @returns Query result with audit logs data, loading state, and error
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useAuditLogs()
 *
 * // With filters
 * const { data } = useAuditLogs({ action_type: 'execution_started', limit: 25 })
 *
 * // Access the audit logs array and pagination info
 * const logs = data?.results?.entries ?? []
 * const totalCount = data?.results?.total_count ?? 0
 * ```
 */
export function useAuditLogs(
  filters?: AuditLogFilters,
  options?: Omit<
    UseQueryOptions<ApiResponse<PaginatedResponse<AuditLogEntry>>, ApiError>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery({
    queryKey: auditLogsKeys.list(filters),
    queryFn: () => apiClient.getAuditLogs(filters),
    ...options,
  })
}
