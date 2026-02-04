/**
 * React Query mutation hooks for service CRUD operations
 *
 * These hooks provide optimistic updates, automatic cache invalidation,
 * and proper error handling for service mutations.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient, type Service, type ApiResponse, type ApiError } from '@/lib/api'
import { servicesKeys } from './use-services'

// ============================================================================
// Types
// ============================================================================

/**
 * Input type for updating a service
 */
export interface UpdateServiceInput {
  heartbeatName: string
  updates: Partial<{
    service_name: string
    muted: number
    active: number
    alert_interval: number
    threshold: number
    team: string
    priority: string
    runbook: string
    down: number
  }>
}

/**
 * Input type for creating a service
 */
export interface CreateServiceInput {
  heartbeat_name: string
  service_name: string
  alert_interval: number
  environment?: string
  threshold?: number
  team?: string
  priority?: string
  runbook?: string
}

/**
 * Input type for bulk updating services
 */
export interface BulkUpdateServicesInput {
  heartbeatNames: string[]
  updates: Partial<{
    muted: number
    active: number
    team: string
    priority: string
  }>
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook for updating a single service with optimistic updates
 *
 * @returns Mutation object with mutate/mutateAsync functions
 *
 * @example
 * ```tsx
 * const { mutate, isPending } = useUpdateService()
 *
 * // Update a service
 * mutate({
 *   heartbeatName: 'my-service',
 *   updates: { muted: 1 }
 * })
 *
 * // With callbacks
 * mutate(
 *   { heartbeatName: 'my-service', updates: { priority: 'p1' } },
 *   {
 *     onSuccess: () => toast.success('Service updated'),
 *     onError: (error) => toast.error(error.message)
 *   }
 * )
 * ```
 */
export function useUpdateService() {
  const queryClient = useQueryClient()

  return useMutation<ApiResponse<string>, ApiError, UpdateServiceInput, { previousServices?: ApiResponse<Service[]> }>({
    mutationFn: async ({ heartbeatName, updates }) => {
      return apiClient.updateService(heartbeatName, updates)
    },

    // Optimistic update: immediately update the cache before the request completes
    onMutate: async ({ heartbeatName, updates }) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: servicesKeys.all })

      // Snapshot the previous value
      const previousServices = queryClient.getQueryData<ApiResponse<Service[]>>(servicesKeys.lists())

      // Optimistically update the service in the list cache
      if (previousServices) {
        queryClient.setQueryData<ApiResponse<Service[]>>(servicesKeys.lists(), {
          ...previousServices,
          results: previousServices.results.map((service) =>
            service.heartbeat_name === heartbeatName
              ? { ...service, ...updates, date_modified: new Date().toISOString() }
              : service
          ),
        })
      }

      // Also update the detail cache if it exists
      const previousDetail = queryClient.getQueryData<ApiResponse<Service[]>>(
        servicesKeys.detail(heartbeatName)
      )
      if (previousDetail?.results?.[0]) {
        queryClient.setQueryData<ApiResponse<Service[]>>(servicesKeys.detail(heartbeatName), {
          ...previousDetail,
          results: [{ ...previousDetail.results[0], ...updates, date_modified: new Date().toISOString() }],
        })
      }

      // Return context with previous value for rollback
      return { previousServices }
    },

    // If mutation fails, rollback to previous value
    onError: (_error, { heartbeatName }, context) => {
      if (context?.previousServices) {
        queryClient.setQueryData(servicesKeys.lists(), context.previousServices)
      }
      // Invalidate detail query to refetch correct data
      queryClient.invalidateQueries({ queryKey: servicesKeys.detail(heartbeatName) })
    },

    // Always invalidate queries after mutation settles to ensure fresh data
    onSettled: (_data, _error, { heartbeatName }) => {
      queryClient.invalidateQueries({ queryKey: servicesKeys.lists() })
      queryClient.invalidateQueries({ queryKey: servicesKeys.detail(heartbeatName) })
    },
  })
}

/**
 * Hook for creating a new service
 *
 * @returns Mutation object with mutate/mutateAsync functions
 *
 * @example
 * ```tsx
 * const { mutate, isPending } = useCreateService()
 *
 * // Create a service
 * mutate({
 *   heartbeat_name: 'new-service',
 *   service_name: 'New Service',
 *   alert_interval: 5,
 *   team: 'platform',
 *   priority: 'p3'
 * })
 * ```
 */
export function useCreateService() {
  const queryClient = useQueryClient()

  return useMutation<ApiResponse<string>, ApiError, CreateServiceInput>({
    mutationFn: async (service) => {
      return apiClient.createService(service)
    },

    // Invalidate services list on success to refetch with new service
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: servicesKeys.lists() })
    },
  })
}

/**
 * Hook for bulk updating multiple services
 *
 * @returns Mutation object with mutate/mutateAsync functions
 *
 * @example
 * ```tsx
 * const { mutate, isPending } = useBulkUpdateServices()
 *
 * // Mute multiple services
 * mutate({
 *   heartbeatNames: ['service-1', 'service-2', 'service-3'],
 *   updates: { muted: 1 }
 * })
 *
 * // Change team for multiple services
 * mutate({
 *   heartbeatNames: selectedServices,
 *   updates: { team: 'platform' }
 * })
 * ```
 */
export function useBulkUpdateServices() {
  const queryClient = useQueryClient()

  return useMutation<
    { succeeded: string[]; failed: Array<{ heartbeatName: string; error: string }> },
    ApiError,
    BulkUpdateServicesInput,
    { previousServices?: ApiResponse<Service[]> }
  >({
    mutationFn: async ({ heartbeatNames, updates }) => {
      const results = await Promise.allSettled(
        heartbeatNames.map((heartbeatName) => apiClient.updateService(heartbeatName, updates))
      )

      const succeeded: string[] = []
      const failed: Array<{ heartbeatName: string; error: string }> = []

      results.forEach((result, index) => {
        const heartbeatName = heartbeatNames[index]
        if (result.status === 'fulfilled') {
          succeeded.push(heartbeatName)
        } else {
          failed.push({
            heartbeatName,
            error: result.reason?.message || 'Unknown error',
          })
        }
      })

      // If all failed, throw error
      if (succeeded.length === 0 && failed.length > 0) {
        throw new Error(`All ${failed.length} updates failed`)
      }

      return { succeeded, failed }
    },

    // Optimistic update for bulk operations
    onMutate: async ({ heartbeatNames, updates }) => {
      await queryClient.cancelQueries({ queryKey: servicesKeys.all })

      const previousServices = queryClient.getQueryData<ApiResponse<Service[]>>(servicesKeys.lists())

      if (previousServices) {
        queryClient.setQueryData<ApiResponse<Service[]>>(servicesKeys.lists(), {
          ...previousServices,
          results: previousServices.results.map((service) =>
            heartbeatNames.includes(service.heartbeat_name)
              ? { ...service, ...updates, date_modified: new Date().toISOString() }
              : service
          ),
        })
      }

      return { previousServices }
    },

    // Rollback on error
    onError: (_error, _variables, context) => {
      if (context?.previousServices) {
        queryClient.setQueryData(servicesKeys.lists(), context.previousServices)
      }
    },

    // Always invalidate after mutation
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: servicesKeys.all })
    },
  })
}
