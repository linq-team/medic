import { Link } from 'react-router-dom'
import { AlertTriangle, Bell, Clock, CheckCircle } from 'lucide-react'
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
import { useAlerts } from '@/hooks'
import { cn } from '@/lib/utils'
import type { Alert } from '@/lib/api'

/**
 * Filter configurations for the Alerts table
 */
const ALERT_FILTERS: FilterConfig[] = [
  {
    param: 'active',
    label: 'Status',
    options: [
      { value: 'all', label: 'All' },
      { value: '1', label: 'Active' },
      { value: '0', label: 'Resolved' },
    ],
    placeholder: 'All',
  },
  {
    param: 'priority',
    label: 'Priority',
    options: [
      { value: 'all', label: 'All' },
      { value: 'P1', label: 'P1' },
      { value: 'P2', label: 'P2' },
      { value: 'P3', label: 'P3' },
    ],
    placeholder: 'All',
  },
]

/**
 * Get status badge variant and label for an alert
 */
function getStatusBadge(alert: Alert): { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string; icon: typeof Bell } {
  if (alert.active === 1) {
    return { variant: 'destructive', label: 'Active', icon: Bell }
  }
  return { variant: 'secondary', label: 'Resolved', icon: CheckCircle }
}

/**
 * Get priority badge styling
 */
function getPriorityBadge(priority: string): { className: string; label: string } {
  switch (priority.toLowerCase()) {
    case 'p1':
      return { className: 'bg-status-error text-white', label: 'P1' }
    case 'p2':
      return { className: 'bg-status-warning text-black dark:text-white', label: 'P2' }
    case 'p3':
      return { className: 'bg-muted text-muted-foreground', label: 'P3' }
    default:
      return { className: 'bg-muted text-muted-foreground', label: priority.toUpperCase() }
  }
}

/**
 * Format a duration in seconds to a human-readable string
 */
function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`
  }
  return `${secs}s`
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
 * Empty state when no alerts are found
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Bell className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium text-foreground mb-2">No alerts found</h3>
      <p className="text-muted-foreground max-w-sm">
        There are no alerts yet. Alerts will appear here when services miss their heartbeats.
      </p>
    </div>
  )
}

/**
 * Alerts list page with table displaying all active and historical alerts
 */
export function Alerts() {
  const { data, isLoading, error } = useAlerts()
  const { sortColumn, sortDirection, toggleSort, sortItems } = useSort(
    'sort',
    'dir',
    'created_date', // default sort column
    'desc' // default direction (most recent first)
  )
  const {
    filterState,
    setFilter,
    clearFilters,
    hasActiveFilters,
    filterItems,
  } = useFilter(ALERT_FILTERS)

  const allAlerts = data?.results ?? []

  // Filter first, then sort
  const filteredAlerts = filterItems(allAlerts)
  const alerts = sortItems(filteredAlerts)
  const totalItems = alerts.length

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Alerts</h1>
      <p className="text-muted-foreground mb-8">
        View active and historical alerts for all monitored services.
      </p>

      {error && (
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Error loading alerts</span>
          </div>
          <p className="mt-1 text-sm">
            {error.message || 'Failed to fetch alerts from the API'}
          </p>
        </div>
      )}

      {/* Filter controls */}
      {!isLoading && allAlerts.length > 0 && (
        <TableFilters
          filters={ALERT_FILTERS}
          filterState={filterState}
          onFilterChange={setFilter}
          onClearFilters={clearFilters}
          hasActiveFilters={hasActiveFilters}
        />
      )}

      {isLoading ? (
        <TableSkeleton />
      ) : allAlerts.length === 0 ? (
        <EmptyState />
      ) : totalItems === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Bell className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">No matching alerts</h3>
          <p className="text-muted-foreground max-w-sm mb-4">
            No alerts match your current filters. Try adjusting or clearing them.
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-linq-blue hover:underline text-sm"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableTableHead
                  columnKey="heartbeat_name"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Alert Name
                </SortableTableHead>
                <SortableTableHead
                  columnKey="service_name"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Service
                </SortableTableHead>
                <SortableTableHead
                  columnKey="active"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Status
                </SortableTableHead>
                <SortableTableHead
                  columnKey="priority"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Priority
                </SortableTableHead>
                <SortableTableHead
                  columnKey="created_date"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Created Date
                </SortableTableHead>
                <SortableTableHead
                  columnKey="closed_date"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Closed Date
                </SortableTableHead>
                <SortableTableHead
                  columnKey="duration"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                >
                  Duration
                </SortableTableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {alerts.map((alert) => {
                const statusBadge = getStatusBadge(alert)
                const priorityBadge = getPriorityBadge(alert.priority)
                const StatusIcon = statusBadge.icon

                return (
                  <TableRow key={alert.alert_id}>
                    <TableCell className="font-mono text-sm">
                      <Link
                        to={`/alerts/${alert.alert_id}`}
                        className="hover:underline hover:text-linq-blue"
                      >
                        {alert.heartbeat_name}
                      </Link>
                    </TableCell>
                    <TableCell className="font-medium">
                      <Link
                        to={`/services/${encodeURIComponent(alert.heartbeat_name)}`}
                        className="hover:underline hover:text-linq-blue"
                      >
                        {alert.service_name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={statusBadge.variant}
                        className={cn(
                          'inline-flex items-center gap-1',
                          alert.active === 1 && 'animate-pulse'
                        )}
                      >
                        <StatusIcon className="h-3 w-3" />
                        {statusBadge.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={priorityBadge.className}>
                        {priorityBadge.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {formatDate(alert.created_date)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">
                        {formatDate(alert.closed_date)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="font-mono text-sm">
                        {formatDuration(alert.duration)}
                      </span>
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
