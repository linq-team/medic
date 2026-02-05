/**
 * Hook for showing toast notifications with undo functionality
 *
 * Provides a way to show success toasts for destructive actions with an Undo button
 * that restores the service to its previous state via snapshot.
 */

import { useCallback, useRef, useState } from 'react'
import { toast } from 'sonner'
import { useRestoreSnapshot } from './use-snapshots'
import { apiClient } from '@/lib/api'

// ============================================================================
// Types
// ============================================================================

export interface UndoToastOptions {
  /** The service ID to find the most recent snapshot for */
  serviceId: number
  /** The service name for display purposes */
  serviceName: string
  /** Success message to show (e.g., "Service deactivated") */
  successMessage: string
  /** Description text (optional) */
  description?: string
}

export interface BulkUndoToastOptions {
  /** List of services with their IDs */
  services: Array<{ serviceId: number; serviceName: string }>
  /** Success message to show (e.g., "3 services deactivated") */
  successMessage: string
  /** Description text (optional) */
  description?: string
}

export interface UseUndoToastReturn {
  /** Show a success toast with undo button for a single service */
  showUndoToast: (options: UndoToastOptions) => void
  /** Show a success toast with undo button for bulk operations */
  showBulkUndoToast: (options: BulkUndoToastOptions) => void
  /** Whether an undo operation is currently in progress */
  isRestoring: boolean
}

// ============================================================================
// Constants
// ============================================================================

/** Extended duration for undo toasts (10 seconds) */
const UNDO_TOAST_DURATION = 10000

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook for showing toast notifications with undo functionality.
 *
 * When a destructive action is performed, this shows a toast with an Undo button.
 * Clicking Undo restores the service to its previous state using the most recent snapshot.
 *
 * @returns Object with showUndoToast function and isRestoring state
 *
 * @example
 * ```tsx
 * const { showUndoToast, showBulkUndoToast, isRestoring } = useUndoToast()
 *
 * // After a single destructive action succeeds:
 * showUndoToast({
 *   serviceId: service.service_id,
 *   serviceName: service.service_name,
 *   successMessage: 'Service deactivated',
 *   description: 'Monitoring has been paused'
 * })
 *
 * // After a bulk destructive action succeeds:
 * showBulkUndoToast({
 *   services: selectedServices.map(s => ({ serviceId: s.service_id, serviceName: s.service_name })),
 *   successMessage: '3 services deactivated',
 *   description: 'Monitoring paused for selected services'
 * })
 * ```
 */
export function useUndoToast(): UseUndoToastReturn {
  const { mutateAsync: restoreSnapshot } = useRestoreSnapshot()
  const [isRestoring, setIsRestoring] = useState(false)
  // Track active toast IDs to dismiss them when undo starts
  const activeToastRef = useRef<string | number | null>(null)

  /**
   * Show undo toast for a single service action
   */
  const showUndoToast = useCallback(
    async (options: UndoToastOptions) => {
      const { serviceId, serviceName, successMessage, description } = options

      // First, fetch the most recent snapshot for this service
      // We need to do this because the snapshot is created server-side during the action
      let snapshotId: number | null = null

      try {
        const snapshotsResponse = await apiClient.getSnapshots({
          service_id: serviceId,
          limit: 1,
        })
        const snapshots = snapshotsResponse?.results?.entries ?? []
        if (snapshots.length > 0) {
          snapshotId = snapshots[0].snapshot_id
        }
      } catch {
        // If we can't fetch the snapshot, show toast without undo button
        toast.success(successMessage, { description })
        return
      }

      // If no snapshot found, show toast without undo button
      if (!snapshotId) {
        toast.success(successMessage, { description })
        return
      }

      // Capture the snapshotId for the undo handler
      const capturedSnapshotId = snapshotId

      /**
       * Handle undo button click
       */
      const handleUndo = async () => {
        // Dismiss the current toast immediately
        if (activeToastRef.current) {
          toast.dismiss(activeToastRef.current)
          activeToastRef.current = null
        }

        setIsRestoring(true)

        // Show loading toast
        const loadingToastId = toast.loading(`Restoring ${serviceName}...`)

        try {
          await restoreSnapshot({ snapshotId: capturedSnapshotId })

          // Dismiss loading toast and show success
          toast.dismiss(loadingToastId)
          toast.success('Action undone', {
            description: `${serviceName} has been restored to its previous state`,
          })
        } catch (error) {
          // Dismiss loading toast and show error
          toast.dismiss(loadingToastId)
          const errorMessage = error instanceof Error ? error.message : 'Unknown error'
          toast.error('Failed to undo', {
            description: `Could not restore ${serviceName}: ${errorMessage}`,
          })
        } finally {
          setIsRestoring(false)
        }
      }

      // Show toast with Undo button
      activeToastRef.current = toast.success(successMessage, {
        description,
        duration: UNDO_TOAST_DURATION,
        action: {
          label: 'Undo',
          onClick: handleUndo,
        },
      })
    },
    [restoreSnapshot]
  )

  /**
   * Show undo toast for bulk actions
   */
  const showBulkUndoToast = useCallback(
    async (options: BulkUndoToastOptions) => {
      const { services, successMessage, description } = options

      // Fetch the most recent snapshot for each service
      const snapshotsToRestore: Array<{ snapshotId: number; serviceName: string }> = []

      try {
        // Fetch snapshots for all services in parallel
        const snapshotPromises = services.map(async ({ serviceId, serviceName }) => {
          try {
            const snapshotsResponse = await apiClient.getSnapshots({
              service_id: serviceId,
              limit: 1,
            })
            const snapshots = snapshotsResponse?.results?.entries ?? []
            if (snapshots.length > 0) {
              return { snapshotId: snapshots[0].snapshot_id, serviceName }
            }
          } catch {
            // Individual failures don't block others
          }
          return null
        })

        const results = await Promise.all(snapshotPromises)
        for (const result of results) {
          if (result) {
            snapshotsToRestore.push(result)
          }
        }
      } catch {
        // If we can't fetch any snapshots, show toast without undo button
        toast.success(successMessage, { description })
        return
      }

      // If no snapshots found, show toast without undo button
      if (snapshotsToRestore.length === 0) {
        toast.success(successMessage, { description })
        return
      }

      // Capture the snapshots for the undo handler
      const capturedSnapshots = [...snapshotsToRestore]

      /**
       * Handle undo button click for bulk operations
       */
      const handleBulkUndo = async () => {
        // Dismiss the current toast immediately
        if (activeToastRef.current) {
          toast.dismiss(activeToastRef.current)
          activeToastRef.current = null
        }

        setIsRestoring(true)

        // Show loading toast
        const loadingToastId = toast.loading(`Restoring ${capturedSnapshots.length} services...`)

        try {
          // Restore all snapshots in parallel
          const restorePromises = capturedSnapshots.map(({ snapshotId }) =>
            restoreSnapshot({ snapshotId }).catch(() => null)
          )
          const results = await Promise.all(restorePromises)

          const succeeded = results.filter(Boolean).length
          const failed = capturedSnapshots.length - succeeded

          // Dismiss loading toast
          toast.dismiss(loadingToastId)

          // Show result toast
          if (failed === 0) {
            toast.success('Action undone', {
              description: `${succeeded} service${succeeded !== 1 ? 's' : ''} restored to previous state`,
            })
          } else if (succeeded > 0) {
            toast.warning('Partially undone', {
              description: `${succeeded} restored, ${failed} failed to restore`,
            })
          } else {
            toast.error('Failed to undo', {
              description: 'Could not restore any services',
            })
          }
        } catch (error) {
          // Dismiss loading toast and show error
          toast.dismiss(loadingToastId)
          const errorMessage = error instanceof Error ? error.message : 'Unknown error'
          toast.error('Failed to undo', {
            description: errorMessage,
          })
        } finally {
          setIsRestoring(false)
        }
      }

      // Show toast with Undo button
      activeToastRef.current = toast.success(successMessage, {
        description,
        duration: UNDO_TOAST_DURATION,
        action: {
          label: 'Undo',
          onClick: handleBulkUndo,
        },
      })
    },
    [restoreSnapshot]
  )

  return { showUndoToast, showBulkUndoToast, isRestoring }
}
