/**
 * ServiceEditModal Component
 *
 * A modal dialog for editing service properties. Provides a form with validation
 * for editing service_name, team, priority, alert_interval, threshold, and runbook.
 */

import { useState, useMemo, type FormEvent } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUpdateService } from '@/hooks/use-service-mutations'
import type { Service } from '@/lib/api'

// ============================================================================
// Types
// ============================================================================

export interface ServiceEditModalProps {
  /** The service to edit */
  service: Service
  /** Whether the modal is open */
  open: boolean
  /** Callback when modal should close */
  onOpenChange: (open: boolean) => void
}

interface FormErrors {
  service_name?: string
  team?: string
  alert_interval?: string
  threshold?: string
  runbook?: string
}

interface FormData {
  service_name: string
  team: string
  priority: string
  alert_interval: string
  threshold: string
  runbook: string
}

// ============================================================================
// Constants
// ============================================================================

/** Priority options with labels */
const PRIORITY_OPTIONS = [
  { value: 'p1', label: 'P1 - Critical' },
  { value: 'p2', label: 'P2 - High' },
  { value: 'p3', label: 'P3 - Normal' },
] as const

// ============================================================================
// Validation
// ============================================================================

/**
 * Validate the form data and return any errors
 */
function validateForm(data: FormData): FormErrors {
  const errors: FormErrors = {}

  // Service name is required
  if (!data.service_name.trim()) {
    errors.service_name = 'Service name is required'
  } else if (data.service_name.length > 255) {
    errors.service_name = 'Service name must be 255 characters or less'
  }

  // Team validation (optional but if provided, check length)
  if (data.team.length > 100) {
    errors.team = 'Team name must be 100 characters or less'
  }

  // Alert interval must be a positive integer
  const alertInterval = parseInt(data.alert_interval, 10)
  if (isNaN(alertInterval) || alertInterval < 1) {
    errors.alert_interval = 'Alert interval must be at least 1 minute'
  } else if (alertInterval > 10080) {
    // Max 1 week in minutes
    errors.alert_interval = 'Alert interval must be 10080 minutes (1 week) or less'
  }

  // Threshold must be a positive integer
  const threshold = parseInt(data.threshold, 10)
  if (isNaN(threshold) || threshold < 1) {
    errors.threshold = 'Threshold must be at least 1'
  } else if (threshold > 100) {
    errors.threshold = 'Threshold must be 100 or less'
  }

  // Runbook URL validation (optional)
  if (data.runbook.trim()) {
    try {
      new URL(data.runbook)
    } catch {
      errors.runbook = 'Runbook must be a valid URL'
    }
  }

  return errors
}

/**
 * Create initial form data from a service
 */
function getInitialFormData(service: Service): FormData {
  return {
    service_name: service.service_name,
    team: service.team || '',
    priority: service.priority.toLowerCase(),
    alert_interval: String(service.alert_interval),
    threshold: String(service.threshold),
    runbook: service.runbook || '',
  }
}

// ============================================================================
// Internal Form Component
// ============================================================================

interface ServiceEditFormProps {
  service: Service
  onOpenChange: (open: boolean) => void
}

/**
 * Internal form component that manages its own state.
 * Mounted fresh when modal opens via key prop.
 */
function ServiceEditForm({ service, onOpenChange }: ServiceEditFormProps) {
  const { mutate: updateService, isPending } = useUpdateService()

  // Initialize form with service data
  const [formData, setFormData] = useState<FormData>(() => getInitialFormData(service))
  const [touched, setTouched] = useState<Record<string, boolean>>({})

  // Compute validation errors from form data (not in useEffect)
  const errors = useMemo(() => validateForm(formData), [formData])

  // Check if form has changes
  const hasChanges = useMemo(() => {
    return (
      formData.service_name !== service.service_name ||
      formData.team !== (service.team || '') ||
      formData.priority !== service.priority.toLowerCase() ||
      formData.alert_interval !== String(service.alert_interval) ||
      formData.threshold !== String(service.threshold) ||
      formData.runbook !== (service.runbook || '')
    )
  }, [formData, service])

  // Check if form is valid
  const isValid = Object.keys(errors).length === 0

  // Can submit if valid and has changes
  const canSubmit = isValid && hasChanges && !isPending

  /**
   * Handle input field changes
   */
  function handleInputChange(field: keyof FormData, value: string) {
    setFormData((prev) => ({ ...prev, [field]: value }))
    setTouched((prev) => ({ ...prev, [field]: true }))
  }

  /**
   * Handle form submission
   */
  function handleSubmit(e: FormEvent) {
    e.preventDefault()

    if (!canSubmit) return

    // Mark all fields as touched for validation display
    setTouched({
      service_name: true,
      team: true,
      alert_interval: true,
      threshold: true,
      runbook: true,
    })

    // Re-validate (already computed, but check here for clarity)
    if (Object.keys(errors).length > 0) {
      return
    }

    // Build update payload
    const updates: Record<string, string | number> = {}

    if (formData.service_name !== service.service_name) {
      updates.service_name = formData.service_name.trim()
    }
    if (formData.team !== (service.team || '')) {
      updates.team = formData.team.trim()
    }
    if (formData.priority !== service.priority.toLowerCase()) {
      updates.priority = formData.priority
    }
    if (formData.alert_interval !== String(service.alert_interval)) {
      updates.alert_interval = parseInt(formData.alert_interval, 10)
    }
    if (formData.threshold !== String(service.threshold)) {
      updates.threshold = parseInt(formData.threshold, 10)
    }
    if (formData.runbook !== (service.runbook || '')) {
      updates.runbook = formData.runbook.trim()
    }

    updateService(
      {
        heartbeatName: service.heartbeat_name,
        updates,
      },
      {
        onSuccess: () => {
          toast.success('Service updated', {
            description: `${service.service_name} has been updated successfully.`,
          })
          onOpenChange(false)
        },
        onError: (error) => {
          toast.error('Failed to update service', {
            description: error.message || 'An unexpected error occurred.',
          })
        },
      }
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Service Name */}
      <div className="space-y-2">
        <Label htmlFor="service_name">Service Name *</Label>
        <Input
          id="service_name"
          value={formData.service_name}
          onChange={(e) => handleInputChange('service_name', e.target.value)}
          placeholder="Enter service name"
          aria-invalid={touched.service_name && !!errors.service_name}
          aria-describedby={errors.service_name ? 'service_name-error' : undefined}
        />
        {touched.service_name && errors.service_name && (
          <p id="service_name-error" className="text-sm text-destructive">
            {errors.service_name}
          </p>
        )}
      </div>

      {/* Team */}
      <div className="space-y-2">
        <Label htmlFor="team">Team</Label>
        <Input
          id="team"
          value={formData.team}
          onChange={(e) => handleInputChange('team', e.target.value)}
          placeholder="Enter team name"
          aria-invalid={touched.team && !!errors.team}
          aria-describedby={errors.team ? 'team-error' : undefined}
        />
        {touched.team && errors.team && (
          <p id="team-error" className="text-sm text-destructive">
            {errors.team}
          </p>
        )}
      </div>

      {/* Priority */}
      <div className="space-y-2">
        <Label htmlFor="priority">Priority</Label>
        <Select
          value={formData.priority}
          onValueChange={(value) => handleInputChange('priority', value)}
        >
          <SelectTrigger id="priority">
            <SelectValue placeholder="Select priority" />
          </SelectTrigger>
          <SelectContent>
            {PRIORITY_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Alert Interval */}
      <div className="space-y-2">
        <Label htmlFor="alert_interval">Alert Interval (minutes) *</Label>
        <Input
          id="alert_interval"
          type="number"
          min="1"
          max="10080"
          value={formData.alert_interval}
          onChange={(e) => handleInputChange('alert_interval', e.target.value)}
          placeholder="5"
          aria-invalid={touched.alert_interval && !!errors.alert_interval}
          aria-describedby={errors.alert_interval ? 'alert_interval-error' : undefined}
        />
        {touched.alert_interval && errors.alert_interval && (
          <p id="alert_interval-error" className="text-sm text-destructive">
            {errors.alert_interval}
          </p>
        )}
      </div>

      {/* Threshold */}
      <div className="space-y-2">
        <Label htmlFor="threshold">Threshold (missed heartbeats) *</Label>
        <Input
          id="threshold"
          type="number"
          min="1"
          max="100"
          value={formData.threshold}
          onChange={(e) => handleInputChange('threshold', e.target.value)}
          placeholder="1"
          aria-invalid={touched.threshold && !!errors.threshold}
          aria-describedby={errors.threshold ? 'threshold-error' : undefined}
        />
        {touched.threshold && errors.threshold && (
          <p id="threshold-error" className="text-sm text-destructive">
            {errors.threshold}
          </p>
        )}
      </div>

      {/* Runbook */}
      <div className="space-y-2">
        <Label htmlFor="runbook">Runbook URL</Label>
        <Input
          id="runbook"
          type="url"
          value={formData.runbook}
          onChange={(e) => handleInputChange('runbook', e.target.value)}
          placeholder="https://example.com/runbook"
          aria-invalid={touched.runbook && !!errors.runbook}
          aria-describedby={errors.runbook ? 'runbook-error' : undefined}
        />
        {touched.runbook && errors.runbook && (
          <p id="runbook-error" className="text-sm text-destructive">
            {errors.runbook}
          </p>
        )}
      </div>

      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={() => onOpenChange(false)}
          disabled={isPending}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={!canSubmit}>
          {isPending ? 'Saving...' : 'Save Changes'}
        </Button>
      </DialogFooter>
    </form>
  )
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * Modal dialog for editing a service's properties.
 *
 * Uses a key prop on the internal form to reset state when the modal opens.
 * This avoids the need for useEffect to reset form state.
 *
 * @example
 * ```tsx
 * const [open, setOpen] = useState(false)
 *
 * <ServiceEditModal
 *   service={selectedService}
 *   open={open}
 *   onOpenChange={setOpen}
 * />
 * ```
 */
export function ServiceEditModal({
  service,
  open,
  onOpenChange,
}: ServiceEditModalProps) {
  // Track when modal was last opened to use as key for form reset
  const [openCount, setOpenCount] = useState(0)

  // Handle open change - increment counter when opening
  function handleOpenChange(newOpen: boolean) {
    if (newOpen && !open) {
      // Modal is opening - increment counter to reset form
      setOpenCount((c) => c + 1)
    }
    onOpenChange(newOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Edit Service</DialogTitle>
          <DialogDescription>
            Update the settings for {service.service_name}. Click save when you're done.
          </DialogDescription>
        </DialogHeader>

        {/* Key prop resets form state when modal opens */}
        <ServiceEditForm
          key={`${service.heartbeat_name}-${openCount}`}
          service={service}
          onOpenChange={onOpenChange}
        />
      </DialogContent>
    </Dialog>
  )
}
