/**
 * Service Toggle Components
 *
 * Provides inline toggle switches for service mute and active status
 * with optimistic updates and confirmation dialogs for destructive actions.
 */

import { useState } from 'react'
import { toast } from 'sonner'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useUpdateService } from '@/hooks/use-service-mutations'
import type { Service } from '@/lib/api'

interface ServiceToggleProps {
  service: Service
}

/**
 * Mute toggle switch for a service
 *
 * Immediately toggles mute status with optimistic updates.
 * No confirmation needed as muting is non-destructive.
 */
export function MuteToggle({ service }: ServiceToggleProps) {
  const { mutate, isPending } = useUpdateService()
  const isMuted = service.muted === 1

  const handleToggle = (checked: boolean) => {
    const newMuted = checked ? 1 : 0

    mutate(
      {
        heartbeatName: service.heartbeat_name,
        updates: { muted: newMuted },
      },
      {
        onSuccess: () => {
          toast.success(
            checked
              ? `${service.service_name} muted - alerts silenced`
              : `${service.service_name} unmuted - alerts enabled`
          )
        },
        onError: (error) => {
          toast.error(`Failed to update ${service.service_name}: ${error.message}`)
        },
      }
    )
  }

  return (
    <div className="flex items-center">
      <Switch
        checked={isMuted}
        onCheckedChange={handleToggle}
        disabled={isPending}
        aria-label={`${isMuted ? 'Unmute' : 'Mute'} ${service.service_name}`}
      />
    </div>
  )
}

/**
 * Active toggle switch for a service
 *
 * Shows confirmation dialog before deactivating to prevent accidental changes.
 * Deactivation creates a snapshot for potential restoration.
 */
export function ActiveToggle({ service }: ServiceToggleProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const { mutate, isPending } = useUpdateService()
  const isActive = service.active === 1

  const handleToggle = (checked: boolean) => {
    if (!checked) {
      // Deactivating requires confirmation
      setShowConfirmDialog(true)
    } else {
      // Activating does not require confirmation
      performUpdate(1)
    }
  }

  const performUpdate = (newActive: number) => {
    mutate(
      {
        heartbeatName: service.heartbeat_name,
        updates: { active: newActive },
      },
      {
        onSuccess: () => {
          toast.success(
            newActive === 1
              ? `${service.service_name} activated - monitoring resumed`
              : `${service.service_name} deactivated - monitoring paused`
          )
          setShowConfirmDialog(false)
        },
        onError: (error) => {
          toast.error(`Failed to update ${service.service_name}: ${error.message}`)
          setShowConfirmDialog(false)
        },
      }
    )
  }

  const handleConfirmDeactivate = () => {
    performUpdate(0)
  }

  return (
    <>
      <div className="flex items-center">
        <Switch
          checked={isActive}
          onCheckedChange={handleToggle}
          disabled={isPending}
          aria-label={`${isActive ? 'Deactivate' : 'Activate'} ${service.service_name}`}
        />
      </div>

      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Deactivate Service</DialogTitle>
            <DialogDescription>
              Are you sure you want to deactivate <strong>{service.service_name}</strong>?
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              Deactivating this service will:
            </p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground list-disc list-inside">
              <li>Stop monitoring heartbeats</li>
              <li>Prevent new alerts from being created</li>
              <li>Keep historical data intact</li>
            </ul>
            <p className="mt-3 text-sm text-muted-foreground">
              A snapshot will be created so you can restore if needed.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDeactivate}
              disabled={isPending}
            >
              {isPending ? 'Deactivating...' : 'Deactivate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
