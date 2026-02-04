/**
 * Shared constants for the Medic UI
 */

// ============================================================================
// Priority Options
// ============================================================================

/**
 * Priority option definition for forms and selectors
 */
export interface PriorityOption {
  /** Value stored in database (lowercase) */
  value: string
  /** Short display label */
  label: string
  /** Extended label with description */
  labelWithDescription: string
  /** Tailwind class for color styling */
  className: string
}

/**
 * Priority options with color styling
 *
 * Used across:
 * - PrioritySelector (inline table selector)
 * - ServiceEditModal (edit form)
 * - ServiceCreateModal (create form)
 * - BulkActionsToolbar (bulk priority change)
 */
export const PRIORITY_OPTIONS: readonly PriorityOption[] = [
  {
    value: 'p1',
    label: 'P1',
    labelWithDescription: 'P1 - Critical',
    className: 'text-status-error'
  },
  {
    value: 'p2',
    label: 'P2',
    labelWithDescription: 'P2 - High',
    className: 'text-status-warning'
  },
  {
    value: 'p3',
    label: 'P3',
    labelWithDescription: 'P3 - Normal',
    className: 'text-muted-foreground'
  },
] as const

/**
 * Get the priority class name for styling
 */
export function getPriorityClassName(priority: string): string {
  const option = PRIORITY_OPTIONS.find(
    (opt) => opt.value.toLowerCase() === priority.toLowerCase()
  )
  return option?.className ?? 'text-muted-foreground'
}

/**
 * Get full priority option by value
 */
export function getPriorityOption(priority: string): PriorityOption | undefined {
  return PRIORITY_OPTIONS.find(
    (opt) => opt.value.toLowerCase() === priority.toLowerCase()
  )
}
