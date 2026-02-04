/**
 * ServiceCreateModal Component
 *
 * A modal dialog for creating new services. Provides a form with validation
 * for creating services with heartbeat_name, service_name, team, priority,
 * alert_interval, threshold, and runbook fields.
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
import { useCreateService } from '@/hooks/use-service-mutations'
import { PRIORITY_OPTIONS } from '@/lib/constants'

// ============================================================================
// Types
// ============================================================================

export interface ServiceCreateModalProps {
  /** Whether the modal is open */
  open: boolean
  /** Callback when modal should close */
  onOpenChange: (open: boolean) => void
}

interface FormErrors {
  heartbeat_name?: string
  service_name?: string
  team?: string
  alert_interval?: string
  threshold?: string
  runbook?: string
}

interface FormData {
  heartbeat_name: string
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

/** Default form values for new service */
const DEFAULT_FORM_DATA: FormData = {
  heartbeat_name: '',
  service_name: '',
  team: '',
  priority: 'p3',
  alert_interval: '5',
  threshold: '1',
  runbook: '',
}

// ============================================================================
// Validation
// ============================================================================

/**
 * Validate the form data and return any errors
 */
function validateForm(data: FormData): FormErrors {
  const errors: FormErrors = {}

  // Heartbeat name is required and must be valid identifier
  if (!data.heartbeat_name.trim()) {
    errors.heartbeat_name = 'Heartbeat name is required'
  } else if (data.heartbeat_name.length > 255) {
    errors.heartbeat_name = 'Heartbeat name must be 255 characters or less'
  } else if (!/^[a-zA-Z0-9_-]+$/.test(data.heartbeat_name)) {
    errors.heartbeat_name = 'Heartbeat name can only contain letters, numbers, hyphens, and underscores'
  }

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

// ============================================================================
// Internal Form Component
// ============================================================================

interface ServiceCreateFormProps {
  onOpenChange: (open: boolean) => void
}

/**
 * Internal form component that manages its own state.
 * Mounted fresh when modal opens via key prop.
 */
function ServiceCreateForm({ onOpenChange }: ServiceCreateFormProps) {
  const { mutate: createService, isPending } = useCreateService()

  // Initialize form with default data
  const [formData, setFormData] = useState<FormData>(DEFAULT_FORM_DATA)
  const [touched, setTouched] = useState<Record<string, boolean>>({})

  // Compute validation errors from form data (not in useEffect)
  const errors = useMemo(() => validateForm(formData), [formData])

  // Check if form has required fields filled
  const hasRequiredFields = useMemo(() => {
    return (
      formData.heartbeat_name.trim() !== '' &&
      formData.service_name.trim() !== ''
    )
  }, [formData.heartbeat_name, formData.service_name])

  // Check if form is valid
  const isValid = Object.keys(errors).length === 0

  // Can submit if valid and has required fields
  const canSubmit = isValid && hasRequiredFields && !isPending

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
      heartbeat_name: true,
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

    // Build create payload
    const serviceData = {
      heartbeat_name: formData.heartbeat_name.trim(),
      service_name: formData.service_name.trim(),
      alert_interval: parseInt(formData.alert_interval, 10),
      threshold: parseInt(formData.threshold, 10),
      priority: formData.priority,
      team: formData.team.trim() || undefined,
      runbook: formData.runbook.trim() || undefined,
    }

    createService(serviceData, {
      onSuccess: () => {
        toast.success('Service created', {
          description: `${formData.service_name} has been created successfully.`,
        })
        onOpenChange(false)
      },
      onError: (error) => {
        // Check for duplicate heartbeat_name error
        const errorMessage = error.message || 'An unexpected error occurred.'
        if (errorMessage.toLowerCase().includes('already exists') ||
            errorMessage.toLowerCase().includes('duplicate')) {
          toast.error('Service already exists', {
            description: `A service with heartbeat name "${formData.heartbeat_name}" already exists.`,
          })
        } else {
          toast.error('Failed to create service', {
            description: errorMessage,
          })
        }
      },
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Heartbeat Name */}
      <div className="space-y-2">
        <Label htmlFor="heartbeat_name">Heartbeat Name *</Label>
        <Input
          id="heartbeat_name"
          value={formData.heartbeat_name}
          onChange={(e) => handleInputChange('heartbeat_name', e.target.value)}
          placeholder="my-service-heartbeat"
          aria-invalid={touched.heartbeat_name && !!errors.heartbeat_name}
          aria-describedby={errors.heartbeat_name ? 'heartbeat_name-error' : 'heartbeat_name-hint'}
        />
        <p id="heartbeat_name-hint" className="text-xs text-muted-foreground">
          Unique identifier used for API calls. Only letters, numbers, hyphens, and underscores.
        </p>
        {touched.heartbeat_name && errors.heartbeat_name && (
          <p id="heartbeat_name-error" className="text-sm text-destructive">
            {errors.heartbeat_name}
          </p>
        )}
      </div>

      {/* Service Name */}
      <div className="space-y-2">
        <Label htmlFor="service_name">Service Name *</Label>
        <Input
          id="service_name"
          value={formData.service_name}
          onChange={(e) => handleInputChange('service_name', e.target.value)}
          placeholder="My Service"
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
                {option.labelWithDescription}
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
          {isPending ? 'Creating...' : 'Create Service'}
        </Button>
      </DialogFooter>
    </form>
  )
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * Modal dialog for creating a new service.
 *
 * Uses a key prop on the internal form to reset state when the modal opens.
 * This avoids the need for useEffect to reset form state.
 *
 * @example
 * ```tsx
 * const [open, setOpen] = useState(false)
 *
 * <Button onClick={() => setOpen(true)}>Add Service</Button>
 * <ServiceCreateModal
 *   open={open}
 *   onOpenChange={setOpen}
 * />
 * ```
 */
export function ServiceCreateModal({
  open,
  onOpenChange,
}: ServiceCreateModalProps) {
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
          <DialogTitle>Add Service</DialogTitle>
          <DialogDescription>
            Create a new service to monitor. Fill in the details below and click create.
          </DialogDescription>
        </DialogHeader>

        {/* Key prop resets form state when modal opens */}
        <ServiceCreateForm
          key={openCount}
          onOpenChange={onOpenChange}
        />
      </DialogContent>
    </Dialog>
  )
}
