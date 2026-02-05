/**
 * ServiceRowActions Component
 *
 * Dropdown menu for individual service row actions in the Services table.
 * Provides quick access to View Details, Edit, Mute/Unmute, Activate/Deactivate, and View History.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  MoreHorizontal,
  Eye,
  Pencil,
  VolumeX,
  Volume2,
  Power,
  PowerOff,
  History,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ServiceEditModal } from '@/components/service-edit-modal'
import { useUpdateService, useUndoToast } from '@/hooks'
import type { Service } from '@/lib/api'

// ============================================================================
// Types
// ============================================================================

export interface ServiceRowActionsProps {
  /** The service to show actions for */
  service: Service
}

// ============================================================================
// Component
// ============================================================================

/**
 * Row actions dropdown menu for a service in the Services table.
 *
 * Provides a three-dot menu with actions:
 * - View Details: Navigate to service detail page
 * - Edit: Open edit modal
 * - Mute/Unmute: Toggle mute status
 * - Activate/Deactivate: Toggle active status (with confirmation for deactivate)
 * - View History: Navigate to service history (when available)
 *
 * @example
 * ```tsx
 * <ServiceRowActions service={service} />
 * ```
 */
export function ServiceRowActions({ service }: ServiceRowActionsProps) {
  const navigate = useNavigate()
  const { mutate: updateService, isPending } = useUpdateService()
  const { showUndoToast, isRestoring } = useUndoToast()
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [isDeactivateDialogOpen, setIsDeactivateDialogOpen] = useState(false)

  const isDisabled = isPending || isRestoring

  const isMuted = service.muted === 1
  const isActive = service.active === 1

  /**
   * Navigate to service detail page
   */
  function handleViewDetails() {
    navigate(`/services/${encodeURIComponent(service.heartbeat_name)}`)
  }

  /**
   * Toggle mute status
   */
  function handleMuteToggle() {
    const newMuted = isMuted ? 0 : 1
    updateService(
      {
        heartbeatName: service.heartbeat_name,
        updates: { muted: newMuted },
      },
      {
        onSuccess: () => {
          // Muting is a destructive action (silences alerts), so show undo toast
          if (newMuted === 1) {
            showUndoToast({
              serviceId: service.service_id,
              serviceName: service.service_name,
              successMessage: 'Service muted',
              description: `${service.service_name} - alerts silenced`,
            })
          } else {
            toast.success('Service unmuted - alerts enabled', {
              description: service.service_name,
            })
          }
        },
        onError: (error) => {
          toast.error('Failed to update service', {
            description: `${service.service_name}: ${error.message}`
          })
        },
      }
    )
  }

  /**
   * Handle activate - no confirmation needed
   */
  function handleActivate() {
    updateService(
      {
        heartbeatName: service.heartbeat_name,
        updates: { active: 1 },
      },
      {
        onSuccess: () => {
          toast.success('Service activated - monitoring resumed', {
            description: service.service_name
          })
        },
        onError: (error) => {
          toast.error('Failed to activate service', {
            description: `${service.service_name}: ${error.message}`
          })
        },
      }
    )
  }

  /**
   * Handle deactivate after confirmation
   */
  function handleDeactivateConfirm() {
    updateService(
      {
        heartbeatName: service.heartbeat_name,
        updates: { active: 0 },
      },
      {
        onSuccess: () => {
          showUndoToast({
            serviceId: service.service_id,
            serviceName: service.service_name,
            successMessage: 'Service deactivated',
            description: `${service.service_name} - monitoring paused`,
          })
          setIsDeactivateDialogOpen(false)
        },
        onError: (error) => {
          toast.error('Failed to deactivate service', {
            description: `${service.service_name}: ${error.message}`
          })
        },
      }
    )
  }

  /**
   * Navigate to service history
   */
  function handleViewHistory() {
    // History page with service filter
    navigate(`/history?service=${encodeURIComponent(service.heartbeat_name)}`)
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="h-8 w-8 p-0"
            aria-label={`Actions for ${service.service_name}`}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={handleViewDetails}>
            <Eye className="mr-2 h-4 w-4" />
            View Details
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setIsEditModalOpen(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem onClick={handleMuteToggle} disabled={isDisabled}>
            {isMuted ? (
              <>
                <Volume2 className="mr-2 h-4 w-4" />
                Unmute
              </>
            ) : (
              <>
                <VolumeX className="mr-2 h-4 w-4" />
                Mute
              </>
            )}
          </DropdownMenuItem>

          {isActive ? (
            <DropdownMenuItem
              onClick={() => setIsDeactivateDialogOpen(true)}
              className="text-destructive focus:text-destructive"
              disabled={isDisabled}
            >
              <PowerOff className="mr-2 h-4 w-4" />
              Deactivate
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem onClick={handleActivate} disabled={isDisabled}>
              <Power className="mr-2 h-4 w-4" />
              Activate
            </DropdownMenuItem>
          )}

          <DropdownMenuSeparator />

          <DropdownMenuItem onClick={handleViewHistory}>
            <History className="mr-2 h-4 w-4" />
            View History
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Edit Modal */}
      <ServiceEditModal
        service={service}
        open={isEditModalOpen}
        onOpenChange={setIsEditModalOpen}
      />

      {/* Deactivate Confirmation Dialog */}
      <Dialog open={isDeactivateDialogOpen} onOpenChange={setIsDeactivateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-destructive">Deactivate Service</DialogTitle>
            <DialogDescription>
              Are you sure you want to deactivate <strong>{service.service_name}</strong>?
              This will stop monitoring and no alerts will be generated for this service.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsDeactivateDialogOpen(false)}
              disabled={isDisabled}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeactivateConfirm}
              disabled={isDisabled}
            >
              {isPending ? 'Deactivating...' : 'Deactivate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
