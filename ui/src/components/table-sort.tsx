/**
 * Table Sorting Component
 *
 * A reusable sorting component that manages sort state via URL query params.
 * Provides SortableTableHead component with visual sort direction indicators.
 */

import { useSearchParams } from 'react-router-dom'
import { ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react'
import { TableHead } from '@/components/ui/table'
import { cn } from '@/lib/utils'

/**
 * Sort direction type
 */
export type SortDirection = 'asc' | 'desc' | null

/**
 * Sort state containing column key and direction
 */
export interface SortState {
  column: string | null
  direction: SortDirection
}

/**
 * Props for the SortableTableHead component
 */
export interface SortableTableHeadProps {
  /** Unique key for this column (used in URL params) */
  columnKey: string
  /** Display label for the column header */
  children: React.ReactNode
  /** Current sort column */
  sortColumn: string | null
  /** Current sort direction */
  sortDirection: SortDirection
  /** Callback when sort is changed */
  onSort: (column: string) => void
  /** Additional className for the header */
  className?: string
}

/**
 * Hook to manage sort state via URL search params
 *
 * @param sortParam - URL query param name for sort column (default: 'sort')
 * @param directionParam - URL query param name for sort direction (default: 'dir')
 * @param defaultColumn - Default column to sort by (optional)
 * @param defaultDirection - Default sort direction (default: 'asc')
 */
export function useSort(
  sortParam = 'sort',
  directionParam = 'dir',
  defaultColumn: string | null = null,
  defaultDirection: SortDirection = 'asc'
) {
  const [searchParams, setSearchParams] = useSearchParams()

  const sortColumn = searchParams.get(sortParam) || defaultColumn
  const sortDirection = (searchParams.get(directionParam) as SortDirection) || defaultDirection

  /**
   * Toggle sort for a column
   * - If clicking a new column, sort ascending
   * - If clicking the same column, toggle: asc -> desc -> (remove sort)
   */
  const toggleSort = (column: string) => {
    const newParams = new URLSearchParams(searchParams)

    if (sortColumn !== column) {
      // New column, set to ascending
      newParams.set(sortParam, column)
      newParams.set(directionParam, 'asc')
    } else if (sortDirection === 'asc') {
      // Same column, ascending -> descending
      newParams.set(directionParam, 'desc')
    } else {
      // Same column, descending -> remove sort (back to default)
      if (defaultColumn) {
        // If there's a default, go back to default
        if (column === defaultColumn) {
          newParams.delete(sortParam)
          newParams.delete(directionParam)
        } else {
          newParams.set(sortParam, defaultColumn)
          newParams.set(directionParam, defaultDirection || 'asc')
        }
      } else {
        newParams.delete(sortParam)
        newParams.delete(directionParam)
      }
    }

    // Reset to page 1 when sorting changes
    newParams.delete('page')

    setSearchParams(newParams)
  }

  /**
   * Generic sort function for arrays
   * Handles string, number, and null values
   */
  function sortItems<T>(items: T[]): T[] {
    if (!sortColumn || !sortDirection) {
      return items
    }

    return [...items].sort((a, b) => {
      const aValue = (a as Record<string, unknown>)[sortColumn]
      const bValue = (b as Record<string, unknown>)[sortColumn]

      // Handle null/undefined values - push to end
      if (aValue == null && bValue == null) return 0
      if (aValue == null) return 1
      if (bValue == null) return -1

      // Compare values
      let comparison = 0
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        comparison = aValue.localeCompare(bValue, undefined, { sensitivity: 'base' })
      } else if (typeof aValue === 'number' && typeof bValue === 'number') {
        comparison = aValue - bValue
      } else {
        // Fallback to string comparison
        comparison = String(aValue).localeCompare(String(bValue))
      }

      return sortDirection === 'desc' ? -comparison : comparison
    })
  }

  return {
    sortColumn,
    sortDirection,
    toggleSort,
    sortItems,
  }
}

/**
 * Sortable Table Head Component
 *
 * Renders a table header cell that can be clicked to sort.
 * Shows visual indicators for sort direction.
 *
 * @example
 * ```tsx
 * const { sortColumn, sortDirection, toggleSort } = useSort()
 *
 * return (
 *   <TableHead>
 *     <SortableTableHead
 *       columnKey="service_name"
 *       sortColumn={sortColumn}
 *       sortDirection={sortDirection}
 *       onSort={toggleSort}
 *     >
 *       Service Name
 *     </SortableTableHead>
 *   </TableHead>
 * )
 * ```
 */
export function SortableTableHead({
  columnKey,
  children,
  sortColumn,
  sortDirection,
  onSort,
  className,
}: SortableTableHeadProps) {
  const isActive = sortColumn === columnKey

  const handleClick = () => {
    onSort(columnKey)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSort(columnKey)
    }
  }

  // Determine sort icon
  const SortIcon = isActive
    ? sortDirection === 'asc'
      ? ArrowUp
      : ArrowDown
    : ArrowUpDown

  return (
    <TableHead
      className={cn(
        'cursor-pointer select-none transition-colors hover:bg-muted/50',
        isActive && 'text-foreground font-medium',
        className
      )}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="columnheader"
      aria-sort={isActive ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <div className="flex items-center gap-1">
        <span>{children}</span>
        <SortIcon
          className={cn(
            'h-4 w-4 shrink-0 transition-opacity',
            isActive ? 'opacity-100 text-linq-blue' : 'opacity-40'
          )}
        />
      </div>
    </TableHead>
  )
}
