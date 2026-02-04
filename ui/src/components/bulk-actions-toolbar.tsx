/**
 * BulkActionsToolbar Component
 *
 * Provides bulk action controls when services are selected in the Services table.
 * Includes actions for mute/unmute, activate/deactivate, and changing priority/team.
 */

import { useState } from 'react'
import { toast } from 'sonner'
import {
  Volume2,
  VolumeX,
  Power,
  PowerOff,
  X,
  AlertTriangle,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useBulkUpdateServices } from '@/hooks/use-service-mutations'
import type { Service } from '@/lib/api'
import { PRIORITY_OPTIONS } from '@/lib/constants'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

export interface BulkActionsToolbarProps {
  /** List of selected services */
  selectedServices: Service[]
  /** Callback to clear selection after action */
  onClearSelection: () => void
}

type ActionType = 'mute' | 'unmute' | 'activate' | 'deactivate' | 'priority' | 'team'

interface DialogState {
  type: ActionType | null
  open: boolean
}

// ============================================================================
// Component
// ============================================================================

/**
 * Toolbar for performing bulk actions on selected services.
 *
 * Displayed when one or more services are selected in the table.
 * Shows selected count and available actions.
 *
 * @example
 * ```tsx
 * <BulkActionsToolbar
 *   selectedServices={selectedServices}
 *   onClearSelection={() => setSelectedIds(new Set())}
 * />
 * ```
 */
export function BulkActionsToolbar({
  selectedServices,
  onClearSelection,
}: BulkActionsToolbarProps) {
  const { mutate: bulkUpdate, isPending } = useBulkUpdateServices()
  const [dialog, setDialog] = useState<DialogState>({ type: null, open: false })
  const [newPriority, setNewPriority] = useState<string>('p3')
  const [newTeam, setNewTeam] = useState<string>('')

  const count = selectedServices.length
  const heartbeatNames = selectedServices.map((s) => s.heartbeat_name)

  /**
   * Opens confirmation dialog for an action
   */
  function openDialog(type: ActionType) {
    setDialog({ type, open: true })
    // Reset form values
    if (type === 'priority') {
      setNewPriority('p3')
    } else if (type === 'team') {
      setNewTeam('')
    }
  }

  /**
   * Closes the dialog
   */
  function closeDialog() {
    setDialog({ type: null, open: false })
  }

  /**
   * Executes a bulk action
   */
  function executeAction(type: ActionType) {
    let updates: Record<string, number | string>
    let successMessage: string
    let actionLabel: string

    switch (type) {
      case 'mute':
        updates = { muted: 1 }
        successMessage = 'muted'
        actionLabel = 'Mute'
        break
      case 'unmute':
        updates = { muted: 0 }
        successMessage = 'unmuted'
        actionLabel = 'Unmute'
        break
      case 'activate':
        updates = { active: 1 }
        successMessage = 'activated'
        actionLabel = 'Activate'
        break
      case 'deactivate':
        updates = { active: 0 }
        successMessage = 'deactivated'
        actionLabel = 'Deactivate'
        break
      case 'priority':
        updates = { priority: newPriority }
        successMessage = `priority updated to ${newPriority.toUpperCase()}`
        actionLabel = 'Change Priority'
        break
      case 'team':
        updates = { team: newTeam }
        successMessage = newTeam ? `team updated to ${newTeam}` : 'team cleared'
        actionLabel = 'Change Team'
        break
    }

    bulkUpdate(
      { heartbeatNames, updates },
      {
        onSuccess: (result) => {
          const { succeeded, failed } = result

          if (failed.length === 0) {
            toast.success(`${succeeded.length} service${succeeded.length > 1 ? 's' : ''} ${successMessage}`)
          } else if (succeeded.length > 0) {
            toast.warning(`${actionLabel}: ${succeeded.length} succeeded, ${failed.length} failed`, {
              description: `Failed: ${failed.map((f) => f.heartbeatName).join(', ')}`,
            })
          }

          closeDialog()
          onClearSelection()
        },
        onError: (error) => {
          toast.error(`Failed to ${type} services`, {
            description: error.message || 'An unexpected error occurred.',
          })
        },
      }
    )
  }

  /**
   * Get the title for the current dialog
   */
  function getDialogTitle(): string {
    switch (dialog.type) {
      case 'deactivate':
        return 'Deactivate Services'
      case 'mute':
        return 'Mute Services'
      case 'unmute':
        return 'Unmute Services'
      case 'activate':
        return 'Activate Services'
      case 'priority':
        return 'Change Priority'
      case 'team':
        return 'Change Team'
      default:
        return 'Confirm Action'
    }
  }

  /**
   * Get the description for the current dialog
   */
  function getDialogDescription(): string {
    switch (dialog.type) {
      case 'deactivate':
        return `Are you sure you want to deactivate ${count} service${count > 1 ? 's' : ''}? Deactivated services will stop monitoring and won't generate alerts.`
      case 'mute':
        return `Mute ${count} service${count > 1 ? 's' : ''}? They will continue monitoring but won't generate alerts.`
      case 'unmute':
        return `Unmute ${count} service${count > 1 ? 's' : ''}? They will resume generating alerts when down.`
      case 'activate':
        return `Activate ${count} service${count > 1 ? 's' : ''}? They will begin monitoring and alerting.`
      case 'priority':
        return `Change the priority for ${count} service${count > 1 ? 's' : ''}.`
      case 'team':
        return `Change the team for ${count} service${count > 1 ? 's' : ''}.`
      default:
        return ''
    }
  }

  /**
   * Whether the current action is destructive
   */
  function isDestructiveAction(): boolean {
    return dialog.type === 'deactivate'
  }

  if (count === 0) {
    return null
  }

  return (
    <>
      <div className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg border mb-4">
        {/* Selected count */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {count} service{count > 1 ? 's' : ''} selected
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={onClearSelection}
            aria-label="Clear selection"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="h-4 w-px bg-border" />

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => openDialog('mute')}
            disabled={isPending}
          >
            <VolumeX className="h-4 w-4 mr-1" />
            Mute
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => openDialog('unmute')}
            disabled={isPending}
          >
            <Volume2 className="h-4 w-4 mr-1" />
            Unmute
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => openDialog('activate')}
            disabled={isPending}
          >
            <Power className="h-4 w-4 mr-1" />
            Activate
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => openDialog('deactivate')}
            disabled={isPending}
            className="text-destructive hover:text-destructive"
          >
            <PowerOff className="h-4 w-4 mr-1" />
            Deactivate
          </Button>

          <div className="h-4 w-px bg-border" />

          <Button
            variant="outline"
            size="sm"
            onClick={() => openDialog('priority')}
            disabled={isPending}
          >
            Change Priority
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => openDialog('team')}
            disabled={isPending}
          >
            Change Team
          </Button>
        </div>

        {/* Loading indicator */}
        {isPending && (
          <div className="flex items-center gap-2 ml-auto text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Processing...</span>
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      <Dialog open={dialog.open} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className={cn(isDestructiveAction() && 'text-destructive')}>
              {isDestructiveAction() && (
                <AlertTriangle className="h-5 w-5 inline mr-2" />
              )}
              {getDialogTitle()}
            </DialogTitle>
            <DialogDescription>
              {getDialogDescription()}
            </DialogDescription>
          </DialogHeader>

          {/* Service list preview */}
          <div className="max-h-[200px] overflow-y-auto border rounded-md p-2">
            <ul className="space-y-1">
              {selectedServices.map((service) => (
                <li
                  key={service.service_id}
                  className="text-sm text-muted-foreground flex items-center gap-2"
                >
                  <span className="w-2 h-2 rounded-full bg-foreground/30" />
                  {service.service_name}
                  <span className="text-xs opacity-60">({service.heartbeat_name})</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Priority selector for priority action */}
          {dialog.type === 'priority' && (
            <div className="space-y-2 pt-2">
              <Label htmlFor="bulk-priority">New Priority</Label>
              <Select value={newPriority} onValueChange={setNewPriority}>
                <SelectTrigger id="bulk-priority">
                  <SelectValue placeholder="Select priority" />
                </SelectTrigger>
                <SelectContent>
                  {PRIORITY_OPTIONS.map((option) => (
                    <SelectItem
                      key={option.value}
                      value={option.value}
                      className={option.className}
                    >
                      {option.labelWithDescription}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Team input for team action */}
          {dialog.type === 'team' && (
            <div className="space-y-2 pt-2">
              <Label htmlFor="bulk-team">New Team</Label>
              <Input
                id="bulk-team"
                value={newTeam}
                onChange={(e) => setNewTeam(e.target.value)}
                placeholder="Enter team name (leave empty to clear)"
              />
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={closeDialog}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              variant={isDestructiveAction() ? 'destructive' : 'default'}
              onClick={() => dialog.type && executeAction(dialog.type)}
              disabled={isPending}
            >
              {isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {isPending ? 'Processing...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
