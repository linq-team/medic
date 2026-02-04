/**
 * Priority Selector Component
 *
 * Provides an inline compact dropdown selector for changing service priority
 * with optimistic updates and toast notifications.
 */

import { toast } from 'sonner'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUpdateService } from '@/hooks/use-service-mutations'
import type { Service } from '@/lib/api'
import { cn } from '@/lib/utils'

interface PrioritySelectorProps {
  service: Service
}

/**
 * Priority options with color styling
 */
const PRIORITY_OPTIONS = [
  { value: 'P1', label: 'P1', className: 'text-status-error' },
  { value: 'P2', label: 'P2', className: 'text-status-warning' },
  { value: 'P3', label: 'P3', className: 'text-muted-foreground' },
] as const

/**
 * Get priority styling based on value
 */
function getPriorityClassName(priority: string): string {
  const option = PRIORITY_OPTIONS.find(
    (opt) => opt.value.toLowerCase() === priority.toLowerCase()
  )
  return option?.className ?? 'text-muted-foreground'
}

/**
 * Inline priority selector for the Services table
 *
 * Allows users to quickly change a service's priority from a dropdown.
 * Changes are applied immediately with optimistic updates.
 */
export function PrioritySelector({ service }: PrioritySelectorProps) {
  const { mutate, isPending } = useUpdateService()
  const currentPriority = service.priority?.toUpperCase() || 'P3'

  const handlePriorityChange = (newPriority: string) => {
    // Don't update if the value hasn't changed
    if (newPriority.toLowerCase() === currentPriority.toLowerCase()) {
      return
    }

    mutate(
      {
        heartbeatName: service.heartbeat_name,
        updates: { priority: newPriority.toLowerCase() },
      },
      {
        onSuccess: () => {
          toast.success(
            `${service.service_name} priority updated to ${newPriority}`
          )
        },
        onError: (error) => {
          toast.error(
            `Failed to update priority for ${service.service_name}: ${error.message}`
          )
        },
      }
    )
  }

  return (
    <Select
      value={currentPriority}
      onValueChange={handlePriorityChange}
      disabled={isPending}
    >
      <SelectTrigger
        className={cn(
          'h-7 w-16 border-none bg-transparent shadow-none focus:ring-0 px-2',
          getPriorityClassName(currentPriority),
          isPending && 'opacity-50'
        )}
        aria-label={`Change priority for ${service.service_name}`}
      >
        <SelectValue placeholder="Priority" />
      </SelectTrigger>
      <SelectContent>
        {PRIORITY_OPTIONS.map((option) => (
          <SelectItem
            key={option.value}
            value={option.value}
            className={cn('font-medium', option.className)}
          >
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
