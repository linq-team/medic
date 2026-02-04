/**
 * Table Search Component
 *
 * A reusable search component that manages search state via URL query params.
 * Provides useSearch hook and SearchInput component with debounced input.
 */

import { useSearchParams } from 'react-router-dom'
import { useState, useCallback, useRef, useMemo } from 'react'
import { Search, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

/** Default debounce delay in milliseconds */
const DEFAULT_DEBOUNCE_MS = 300

/**
 * Hook to manage search state via URL search params with debouncing
 *
 * @param searchParam - URL query param name for search (default: 'q')
 * @param debounceMs - Debounce delay in milliseconds (default: 300)
 * @returns Search state and methods to update/clear search
 */
export function useSearch(
  searchParam: string = 'q',
  debounceMs: number = DEFAULT_DEBOUNCE_MS
) {
  const [searchParams, setSearchParams] = useSearchParams()

  // Get search term from URL (source of truth for filtering)
  const searchTerm = searchParams.get(searchParam) || ''

  // Local state for input value only used during active typing/debounce
  // When not typing, this will match searchTerm
  const [pendingValue, setPendingValue] = useState<string | null>(null)

  // Debounce timer ref
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // The displayed input value: use pending value if we have one, otherwise URL value
  const inputValue = pendingValue !== null ? pendingValue : searchTerm

  /**
   * Update URL with search term
   */
  const updateUrl = useCallback(
    (value: string) => {
      const newParams = new URLSearchParams(searchParams)

      if (value.trim() === '') {
        newParams.delete(searchParam)
      } else {
        newParams.set(searchParam, value.trim())
      }

      // Reset to page 1 when search changes
      newParams.delete('page')

      setSearchParams(newParams)
      // Clear pending value once URL is updated
      setPendingValue(null)
    },
    [searchParams, searchParam, setSearchParams]
  )

  /**
   * Handle input change with debouncing
   */
  const setSearch = useCallback(
    (value: string) => {
      // Set pending value immediately for responsive UI
      setPendingValue(value)

      // Clear existing timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }

      // Set new timer for debounced URL update
      debounceTimerRef.current = setTimeout(() => {
        updateUrl(value)
      }, debounceMs)
    },
    [debounceMs, updateUrl]
  )

  /**
   * Clear search immediately (no debounce)
   */
  const clearSearch = useCallback(() => {
    // Clear any pending debounce
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    setPendingValue(null)

    const newParams = new URLSearchParams(searchParams)
    newParams.delete(searchParam)
    newParams.delete('page')
    setSearchParams(newParams)
  }, [searchParams, searchParam, setSearchParams])

  /**
   * Check if search is active (based on URL, not pending input)
   */
  const hasSearch = searchTerm.trim() !== ''

  /**
   * Check if input has any value (pending or committed)
   */
  const hasInputValue = inputValue.trim() !== ''

  /**
   * Generic search function for arrays
   * Searches items based on specified fields
   * Uses URL value for filtering (not pending input) for consistency
   */
  const searchItems = useMemo(() => {
    return function searchItemsFn<T>(items: T[], searchFields: (keyof T)[]): T[] {
      if (!hasSearch) {
        return items
      }

      const lowerTerm = searchTerm.toLowerCase()

      return items.filter((item) => {
        for (const field of searchFields) {
          const value = item[field]
          if (value != null && String(value).toLowerCase().includes(lowerTerm)) {
            return true
          }
        }
        return false
      })
    }
  }, [hasSearch, searchTerm])

  return {
    /** Current search term from URL (used for filtering) */
    searchTerm,
    /** Current input value (may differ from searchTerm during debounce) */
    inputValue,
    /** Set search value (debounced) */
    setSearch,
    /** Clear search immediately */
    clearSearch,
    /** Whether search is active (URL has search term) */
    hasSearch,
    /** Whether input has any value (for showing clear button) */
    hasInputValue,
    /** Filter function for searching items */
    searchItems,
  }
}

/**
 * Props for the SearchInput component
 */
export interface SearchInputProps {
  /** Current input value */
  value: string
  /** Callback when input changes */
  onChange: (value: string) => void
  /** Callback to clear search */
  onClear: () => void
  /** Whether to show clear button */
  showClear: boolean
  /** Placeholder text */
  placeholder?: string
  /** Additional className for the container */
  className?: string
}

/**
 * Search Input Component
 *
 * A styled search input with search icon and clear button.
 * Designed to be placed above tables for searching data.
 *
 * @example
 * ```tsx
 * const { inputValue, setSearch, clearSearch, hasInputValue, searchItems } = useSearch()
 *
 * const filteredItems = searchItems(items, ['name', 'description'])
 *
 * return (
 *   <>
 *     <SearchInput
 *       value={inputValue}
 *       onChange={setSearch}
 *       onClear={clearSearch}
 *       showClear={hasInputValue}
 *       placeholder="Search services..."
 *     />
 *     <Table>...</Table>
 *   </>
 * )
 * ```
 */
export function SearchInput({
  value,
  onChange,
  onClear,
  showClear,
  placeholder = 'Search...',
  className,
}: SearchInputProps) {
  return (
    <div className={cn('relative', className)}>
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
      <Input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pl-9 pr-8 h-9 w-full md:w-[300px]"
      />
      {showClear && (
        <button
          type="button"
          onClick={onClear}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-sm hover:bg-accent text-muted-foreground hover:text-foreground"
          aria-label="Clear search"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
