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
import { PRIORITY_OPTIONS, getPriorityClassName } from '@/lib/constants'
import { cn } from '@/lib/utils'

interface PrioritySelectorProps {
  service: Service
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
          toast.success(`Priority updated to ${newPriority}`, {
            description: service.service_name
          })
        },
        onError: (error) => {
          toast.error('Failed to update priority', {
            description: `${service.service_name}: ${error.message}`
          })
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
            value={option.value.toUpperCase()}
            className={cn('font-medium', option.className)}
          >
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
