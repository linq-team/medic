/**
 * Table Filter Component
 *
 * A reusable filter component that manages filter state via URL query params.
 * Provides useFilter hook and TableFilters component with dropdown selects.
 */

import { useSearchParams } from 'react-router-dom'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

/**
 * Filter option for dropdown selects
 */
export interface FilterOption {
  value: string
  label: string
}

/**
 * Filter configuration for a single filter field
 */
export interface FilterConfig {
  /** URL query param name for this filter */
  param: string
  /** Display label for the filter */
  label: string
  /** Available options */
  options: FilterOption[]
  /** Placeholder text when no value selected */
  placeholder?: string
}

/**
 * Filter state as a record of param -> value
 */
export type FilterState = Record<string, string | null>

/**
 * Hook to manage filter state via URL search params
 *
 * @param filters - Array of filter configurations
 * @returns Filter state and methods to update/clear filters
 */
export function useFilter(filters: FilterConfig[]) {
  const [searchParams, setSearchParams] = useSearchParams()

  // Get current filter values from URL
  const filterState: FilterState = {}
  for (const filter of filters) {
    filterState[filter.param] = searchParams.get(filter.param)
  }

  /**
   * Set a single filter value
   */
  const setFilter = (param: string, value: string | null) => {
    const newParams = new URLSearchParams(searchParams)

    if (value === null || value === '' || value === 'all') {
      newParams.delete(param)
    } else {
      newParams.set(param, value)
    }

    // Reset to page 1 when filters change
    newParams.delete('page')

    setSearchParams(newParams)
  }

  /**
   * Clear all filters
   */
  const clearFilters = () => {
    const newParams = new URLSearchParams(searchParams)

    for (const filter of filters) {
      newParams.delete(filter.param)
    }

    // Reset to page 1
    newParams.delete('page')

    setSearchParams(newParams)
  }

  /**
   * Check if any filters are active
   */
  const hasActiveFilters = Object.values(filterState).some(
    (value) => value !== null && value !== '' && value !== 'all'
  )

  /**
   * Get count of active filters
   */
  const activeFilterCount = Object.values(filterState).filter(
    (value) => value !== null && value !== '' && value !== 'all'
  ).length

  /**
   * Generic filter function for arrays
   * Filters items based on current filter state
   */
  function filterItems<T>(items: T[]): T[] {
    return items.filter((item) => {
      for (const filter of filters) {
        const filterValue = filterState[filter.param]
        if (filterValue === null || filterValue === '' || filterValue === 'all') {
          continue
        }

        const itemValue = (item as Record<string, unknown>)[filter.param]

        // Handle numeric comparisons (0/1 for boolean fields)
        if (filterValue === '1' || filterValue === '0') {
          if (Number(itemValue) !== Number(filterValue)) {
            return false
          }
        } else {
          // String comparison
          if (String(itemValue) !== filterValue) {
            return false
          }
        }
      }
      return true
    })
  }

  return {
    filterState,
    setFilter,
    clearFilters,
    hasActiveFilters,
    activeFilterCount,
    filterItems,
  }
}

/**
 * Props for the TableFilters component
 */
export interface TableFiltersProps {
  /** Filter configurations */
  filters: FilterConfig[]
  /** Current filter state */
  filterState: FilterState
  /** Callback when a filter changes */
  onFilterChange: (param: string, value: string | null) => void
  /** Callback to clear all filters */
  onClearFilters: () => void
  /** Whether any filters are active */
  hasActiveFilters: boolean
  /** Additional className for the container */
  className?: string
}

/**
 * Table Filters Component
 *
 * Renders filter dropdowns with a clear filters button.
 * Designed to be placed above tables for filtering data.
 *
 * @example
 * ```tsx
 * const filterConfigs: FilterConfig[] = [
 *   {
 *     param: 'active',
 *     label: 'Status',
 *     options: [
 *       { value: 'all', label: 'All' },
 *       { value: '1', label: 'Active' },
 *       { value: '0', label: 'Inactive' },
 *     ],
 *   },
 * ]
 *
 * const { filterState, setFilter, clearFilters, hasActiveFilters, filterItems } = useFilter(filterConfigs)
 *
 * return (
 *   <>
 *     <TableFilters
 *       filters={filterConfigs}
 *       filterState={filterState}
 *       onFilterChange={setFilter}
 *       onClearFilters={clearFilters}
 *       hasActiveFilters={hasActiveFilters}
 *     />
 *     <Table>...</Table>
 *   </>
 * )
 * ```
 */
export function TableFilters({
  filters,
  filterState,
  onFilterChange,
  onClearFilters,
  hasActiveFilters,
  className,
}: TableFiltersProps) {
  return (
    <div className={cn('flex flex-wrap items-center gap-3 mb-4', className)}>
      {filters.map((filter) => (
        <div key={filter.param} className="flex items-center gap-2">
          <label
            htmlFor={`filter-${filter.param}`}
            className="text-sm font-medium text-muted-foreground whitespace-nowrap"
          >
            {filter.label}:
          </label>
          <Select
            value={filterState[filter.param] || 'all'}
            onValueChange={(value) => onFilterChange(filter.param, value)}
          >
            <SelectTrigger
              id={`filter-${filter.param}`}
              className="w-[130px] h-8 text-sm"
            >
              <SelectValue placeholder={filter.placeholder || 'All'} />
            </SelectTrigger>
            <SelectContent>
              {filter.options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ))}

      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onClearFilters}
          className="h-8 px-2 text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4 mr-1" />
          Clear filters
        </Button>
      )}
    </div>
  )
}
