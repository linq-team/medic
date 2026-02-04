import { AlertTriangle, BookOpen, Clock, Play, Pause, CheckCircle, XCircle, Loader2, HourglassIcon } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { TableFilters, useFilter, type FilterConfig } from '@/components/table-filter'
import { SortableTableHead, useSort } from '@/components/table-sort'
import { SearchInput, useSearch } from '@/components/table-search'
import { usePlaybooks } from '@/hooks'
import { cn } from '@/lib/utils'
import type { Playbook, PlaybookStatus } from '@/lib/api'

/**
 * Filter configurations for the Playbooks table
 */
const PLAYBOOK_FILTERS: FilterConfig[] = [
  {
    param: 'active',
    label: 'Status',
    options: [
      { value: 'all', label: 'All' },
      { value: '1', label: 'Active' },
      { value: '0', label: 'Inactive' },
    ],
    placeholder: 'All',
  },
  {
    param: 'trigger_type',
    label: 'Trigger Type',
    options: [
      { value: 'all', label: 'All' },
      { value: 'alert', label: 'Alert' },
      { value: 'manual', label: 'Manual' },
      { value: 'scheduled', label: 'Scheduled' },
    ],
    placeholder: 'All',
  },
]

/**
 * Get status badge variant and label for a playbook
 */
function getActiveBadge(playbook: Playbook): { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string } {
  if (playbook.active === 0) {
    return { variant: 'secondary', label: 'Inactive' }
  }
  return { variant: 'default', label: 'Active' }
}

/**
 * Get execution status badge styling
 */
function getStatusBadge(status: PlaybookStatus | null): { className: string; label: string; icon: typeof CheckCircle } {
  switch (status) {
    case 'completed':
      return { className: 'bg-status-healthy text-white', label: 'Completed', icon: CheckCircle }
    case 'running':
      return { className: 'bg-linq-blue text-white', label: 'Running', icon: Loader2 }
    case 'pending_approval':
      return { className: 'bg-status-warning text-black dark:text-white', label: 'Pending Approval', icon: HourglassIcon }
    case 'waiting':
      return { className: 'bg-muted text-muted-foreground', label: 'Waiting', icon: Pause }
    case 'failed':
      return { className: 'bg-status-error text-white', label: 'Failed', icon: XCircle }
    case 'cancelled':
      return { className: 'bg-muted text-muted-foreground', label: 'Cancelled', icon: XCircle }
    default:
      return { className: 'bg-muted text-muted-foreground', label: 'Never Run', icon: Play }
  }
}

/**
 * Get trigger type badge styling
 */
function getTriggerBadge(triggerType: string): { className: string; label: string } {
  switch (triggerType.toLowerCase()) {
    case 'alert':
      return { className: 'bg-status-error/20 text-status-error', label: 'Alert' }
    case 'manual':
      return { className: 'bg-linq-blue/20 text-linq-blue', label: 'Manual' }
    case 'scheduled':
      return { className: 'bg-linq-green/20 text-linq-green', label: 'Scheduled' }
    default:
      return { className: 'bg-muted text-muted-foreground', label: triggerType }
  }
}

/**
 * Format a date string to a human-readable format
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '—'

  try {
    const date = new Date(dateString)
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateString
  }
}

/**
 * Loading skeleton for the table
 */
function TableSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
    </div>
  )
}

/**
 * Empty state when no playbooks are found
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium text-foreground mb-2">No playbooks found</h3>
      <p className="text-muted-foreground max-w-sm">
        There are no playbooks configured yet. Playbooks define automated responses to alerts and other events.
      </p>
    </div>
  )
}

/**
 * Playbooks list page with table displaying all playbooks
 */
export function Playbooks() {
  const { data, isLoading, error } = usePlaybooks()
  const { sortColumn, sortDirection, toggleSort, sortItems } = useSort(
    'sort',
    'dir',
    'name', // default sort column
    'asc' // default direction (alphabetical)
  )
  const {
    filterState,
    setFilter,
    clearFilters,
    hasActiveFilters,
    filterItems,
  } = useFilter(PLAYBOOK_FILTERS)
  const {
    inputValue,
    setSearch,
    clearSearch,
    hasSearch,
    hasInputValue,
    searchItems,
  } = useSearch('q', 300)

  const allPlaybooks = data?.results ?? []

  // Search first, then filter, then sort
  const searchedPlaybooks = searchItems(allPlaybooks, ['name', 'description'])
  const filteredPlaybooks = filterItems(searchedPlaybooks)
  const playbooks = sortItems(filteredPlaybooks)
  const totalItems = playbooks.length

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Playbooks</h1>
      <p className="text-muted-foreground mb-8">
        View and manage automated playbooks and their execution history.
      </p>

      {error && (
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Error loading playbooks</span>
          </div>
          <p className="mt-1 text-sm">
            {error.message || 'Failed to fetch playbooks from the API'}
          </p>
        </div>
      )}

      {/* Search and filter controls */}
      {!isLoading && allPlaybooks.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
          <SearchInput
            value={inputValue}
            onChange={setSearch}
            onClear={clearSearch}
            showClear={hasInputValue}
            placeholder="Search by playbook name..."
          />
          <TableFilters
            filters={PLAYBOOK_FILTERS}
            filterState={filterState}
            onFilterChange={setFilter}
            onClearFilters={clearFilters}
            hasActiveFilters={hasActiveFilters}
            className="mb-0"
          />
        </div>
      )}

      {isLoading ? (
        <TableSkeleton />
      ) : allPlaybooks.length === 0 ? (
        <EmptyState />
      ) : totalItems === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">No matching playbooks</h3>
          <p className="text-muted-foreground max-w-sm mb-4">
            No playbooks match your current {hasSearch ? 'search' : ''}{hasSearch && hasActiveFilters ? ' or ' : ''}{hasActiveFilters ? 'filters' : ''}. Try adjusting or clearing {hasSearch && hasActiveFilters ? 'them' : hasSearch ? 'your search' : 'your filters'}.
          </p>
          {(hasSearch || hasActiveFilters) && (
            <div className="flex items-center gap-3">
              {hasSearch && (
                <button
                  onClick={clearSearch}
                  className="text-linq-blue hover:underline text-sm"
                >
                  Clear search
                </button>
              )}
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="text-linq-blue hover:underline text-sm"
                >
                  Clear filters
                </button>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableTableHead
                  columnKey="name"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Name
                </SortableTableHead>
                <SortableTableHead
                  columnKey="description"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Description
                </SortableTableHead>
                <SortableTableHead
                  columnKey="trigger_type"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Trigger Type
                </SortableTableHead>
                <SortableTableHead
                  columnKey="last_run"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Last Run
                </SortableTableHead>
                <SortableTableHead
                  columnKey="status"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Status
                </SortableTableHead>
                <SortableTableHead
                  columnKey="active"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Active
                </SortableTableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {playbooks.map((playbook) => {
                const activeBadge = getActiveBadge(playbook)
                const statusBadge = getStatusBadge(playbook.status)
                const triggerBadge = getTriggerBadge(playbook.trigger_type)
                const StatusIcon = statusBadge.icon

                return (
                  <TableRow key={playbook.playbook_id}>
                    <TableCell className="font-medium">
                      {playbook.name}
                    </TableCell>
                    <TableCell className="text-muted-foreground max-w-xs truncate">
                      {playbook.description || '—'}
                    </TableCell>
                    <TableCell>
                      <Badge className={triggerBadge.className}>
                        {triggerBadge.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {formatDate(playbook.last_run)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={cn(
                          'inline-flex items-center gap-1',
                          statusBadge.className,
                          playbook.status === 'running' && 'animate-pulse'
                        )}
                      >
                        <StatusIcon className={cn('h-3 w-3', playbook.status === 'running' && 'animate-spin')} />
                        {statusBadge.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={activeBadge.variant}>
                        {activeBadge.label}
                      </Badge>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
