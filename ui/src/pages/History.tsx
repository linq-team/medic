import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  AlertTriangle,
  History as HistoryIcon,
  Clock,
  User,
  Calendar,
  X,
  Search,
  RotateCcw,
  CheckCircle,
  Inbox,
  Server,
} from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { useSnapshots, useRestoreSnapshot, type SnapshotFilters } from '@/hooks'
import { cn } from '@/lib/utils'
import type { Snapshot, SnapshotActionType } from '@/lib/api'

/**
 * Available action types for filtering
 */
const ACTION_TYPES: { value: SnapshotActionType | 'all'; label: string }[] = [
  { value: 'all', label: 'All Actions' },
  { value: 'deactivate', label: 'Deactivated' },
  { value: 'activate', label: 'Activated' },
  { value: 'mute', label: 'Muted' },
  { value: 'unmute', label: 'Unmuted' },
  { value: 'edit', label: 'Edited' },
  { value: 'bulk_edit', label: 'Bulk Edited' },
  { value: 'priority_change', label: 'Priority Changed' },
  { value: 'team_change', label: 'Team Changed' },
  { value: 'delete', label: 'Deleted' },
]

/**
 * Get badge styling for action types
 */
function getActionBadge(actionType: SnapshotActionType): { className: string; label: string } {
  switch (actionType) {
    case 'deactivate':
      return { className: 'bg-status-error/20 text-status-error', label: 'Deactivated' }
    case 'activate':
      return { className: 'bg-status-healthy/20 text-status-healthy', label: 'Activated' }
    case 'mute':
      return { className: 'bg-status-warning/20 text-status-warning', label: 'Muted' }
    case 'unmute':
      return { className: 'bg-linq-blue/20 text-linq-blue', label: 'Unmuted' }
    case 'edit':
      return { className: 'bg-linq-blue/20 text-linq-blue', label: 'Edited' }
    case 'bulk_edit':
      return { className: 'bg-linq-blue/20 text-linq-blue', label: 'Bulk Edited' }
    case 'priority_change':
      return { className: 'bg-status-warning/20 text-status-warning', label: 'Priority Changed' }
    case 'team_change':
      return { className: 'bg-linq-green/20 text-linq-green', label: 'Team Changed' }
    case 'delete':
      return { className: 'bg-status-error/20 text-status-error', label: 'Deleted' }
    default:
      return { className: 'bg-muted text-muted-foreground', label: actionType }
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
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
    </div>
  )
}

/**
 * Empty state when no snapshots are found
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Inbox className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium text-foreground mb-2">No history found</h3>
      <p className="text-muted-foreground max-w-sm">
        Service change history will appear here when changes are made to your services.
        Snapshots are created automatically before destructive actions.
      </p>
    </div>
  )
}

/**
 * Page size for pagination
 */
const PAGE_SIZE = 25

/**
 * Calculate the range of page numbers to display
 */
function getPageRange(
  currentPage: number,
  totalPages: number,
  maxButtons: number
): number[] {
  if (totalPages <= maxButtons) {
    return Array.from({ length: totalPages }, (_, i) => i + 1)
  }

  const halfButtons = Math.floor(maxButtons / 2)
  let start = currentPage - halfButtons
  let end = currentPage + halfButtons

  if (start < 1) {
    start = 1
    end = maxButtons
  }

  if (end > totalPages) {
    end = totalPages
    start = totalPages - maxButtons + 1
  }

  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
}

/**
 * History page displaying service change snapshots across all services
 */
export function History() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [showRestoreDialog, setShowRestoreDialog] = useState(false)
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null)

  // Get filter values from URL
  const actionType = searchParams.get('action_type') || ''
  const serviceName = searchParams.get('service') || ''
  const startDate = searchParams.get('start_date') || ''
  const endDate = searchParams.get('end_date') || ''
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10))

  // Local state for debounced service name input
  const [serviceNameInput, setServiceNameInput] = useState(serviceName)

  // Build filters for the API query
  const filters: SnapshotFilters = {
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  }
  if (actionType && actionType !== 'all') {
    filters.action_type = actionType as SnapshotActionType
  }
  if (startDate) {
    filters.start_date = startDate
  }
  if (endDate) {
    filters.end_date = endDate
  }

  const { data, isLoading, error } = useSnapshots(filters)
  const { mutate: restoreSnapshot, isPending: isRestoring } = useRestoreSnapshot()

  // Get snapshots and filter by service name on client side
  // (API doesn't support service name filter, only service_id)
  let snapshots = data?.results?.entries ?? []
  const totalCountFromApi = data?.results?.total_count ?? 0

  // Client-side filter for service name search
  if (serviceName) {
    const lowerServiceName = serviceName.toLowerCase()
    snapshots = snapshots.filter(
      (s) =>
        s.snapshot_data.service_name.toLowerCase().includes(lowerServiceName) ||
        s.snapshot_data.heartbeat_name.toLowerCase().includes(lowerServiceName)
    )
  }

  // Calculate pagination (accounting for client-side filtering)
  const totalCount = serviceName ? snapshots.length : totalCountFromApi
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  // Check if any filters are active
  const hasActiveFilters = !!(actionType && actionType !== 'all') || !!serviceName || !!startDate || !!endDate

  /**
   * Update a filter value in URL params
   */
  const setFilter = (param: string, value: string) => {
    const newParams = new URLSearchParams(searchParams)
    if (!value || value === 'all') {
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
    const newParams = new URLSearchParams()
    setSearchParams(newParams)
    setServiceNameInput('')
  }

  /**
   * Handle service name input change with debounce
   */
  const handleServiceNameChange = (value: string) => {
    setServiceNameInput(value)
    // Debounce the URL update
    const timeoutId = setTimeout(() => {
      setFilter('service', value)
    }, 500)
    return () => clearTimeout(timeoutId)
  }

  /**
   * Handle page change
   */
  const setPage = (newPage: number) => {
    const newParams = new URLSearchParams(searchParams)
    if (newPage === 1) {
      newParams.delete('page')
    } else {
      newParams.set('page', String(newPage))
    }
    setSearchParams(newParams)
  }

  /**
   * Handle restore button click
   */
  const handleRestoreClick = (snapshot: Snapshot) => {
    setSelectedSnapshot(snapshot)
    setShowRestoreDialog(true)
  }

  /**
   * Handle restore confirmation
   */
  const handleRestoreConfirm = () => {
    if (!selectedSnapshot) return

    restoreSnapshot(
      { snapshotId: selectedSnapshot.snapshot_id },
      {
        onSuccess: () => {
          toast.success(
            `${selectedSnapshot.snapshot_data.service_name} restored to ${formatDate(selectedSnapshot.created_at)} state`
          )
          setShowRestoreDialog(false)
          setSelectedSnapshot(null)
        },
        onError: (error) => {
          toast.error(`Failed to restore: ${error.message}`)
          setShowRestoreDialog(false)
          setSelectedSnapshot(null)
        },
      }
    )
  }

  const pageRange = getPageRange(page, totalPages, 5)
  const showStartEllipsis = pageRange[0] > 1
  const showEndEllipsis = pageRange.length > 0 && pageRange[pageRange.length - 1] < totalPages

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Service History</h1>
      <p className="text-muted-foreground mb-8">
        View and restore service changes across all services. Snapshots are created automatically before actions.
      </p>

      {error && (
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Error loading history</span>
          </div>
          <p className="mt-1 text-sm">
            {error.message || 'Failed to fetch snapshots from the API'}
          </p>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 mb-6">
        {/* Service Name Filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">
            Service
          </label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search services..."
              value={serviceNameInput}
              onChange={(e) => handleServiceNameChange(e.target.value)}
              className="pl-8 w-[180px]"
            />
          </div>
        </div>

        {/* Action Type Filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">
            Action Type
          </label>
          <Select
            value={actionType || 'all'}
            onValueChange={(value) => setFilter('action_type', value)}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All Actions" />
            </SelectTrigger>
            <SelectContent>
              {ACTION_TYPES.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Start Date Filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">
            Start Date
          </label>
          <div className="relative">
            <Calendar className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setFilter('start_date', e.target.value)}
              className="pl-8 w-[160px]"
            />
          </div>
        </div>

        {/* End Date Filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">
            End Date
          </label>
          <div className="relative">
            <Calendar className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="date"
              value={endDate}
              onChange={(e) => setFilter('end_date', e.target.value)}
              className="pl-8 w-[160px]"
            />
          </div>
        </div>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="h-9 px-3 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4 mr-1" />
            Clear filters
          </Button>
        )}
      </div>

      {isLoading ? (
        <TableSkeleton />
      ) : snapshots.length === 0 && !hasActiveFilters ? (
        <EmptyState />
      ) : snapshots.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <HistoryIcon className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">No matching history</h3>
          <p className="text-muted-foreground max-w-sm mb-4">
            No snapshots match your current filters. Try adjusting or clearing them.
          </p>
          <button
            onClick={clearFilters}
            className="text-linq-blue hover:underline text-sm"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <>
          {/* Results summary */}
          <div className="text-sm text-muted-foreground mb-4">
            Showing {((page - 1) * PAGE_SIZE) + 1} to {Math.min(page * PAGE_SIZE, totalCount)} of {totalCount} entries
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      <Server className="h-4 w-4" />
                      Service
                    </span>
                  </TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      <User className="h-4 w-4" />
                      Actor
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      Date
                    </span>
                  </TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Restore</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snapshots.map((snapshot) => {
                  const actionBadge = getActionBadge(snapshot.action_type)

                  return (
                    <TableRow key={snapshot.snapshot_id}>
                      <TableCell>
                        <Link
                          to={`/services/${encodeURIComponent(snapshot.snapshot_data.heartbeat_name)}`}
                          className="text-foreground hover:text-linq-blue hover:underline font-medium"
                        >
                          {snapshot.snapshot_data.service_name}
                        </Link>
                        <div className="text-xs text-muted-foreground">
                          {snapshot.snapshot_data.heartbeat_name}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={actionBadge.className}>
                          {actionBadge.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {snapshot.actor || '—'}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {formatDate(snapshot.created_at)}
                      </TableCell>
                      <TableCell>
                        {snapshot.restored_at ? (
                          <Badge variant="secondary" className="inline-flex items-center gap-1">
                            <CheckCircle className="h-3 w-3" />
                            Restored
                          </Badge>
                        ) : (
                          <Badge variant="outline">Available</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {snapshot.restored_at ? (
                          <span className="text-xs text-muted-foreground">
                            {formatDate(snapshot.restored_at)}
                          </span>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRestoreClick(snapshot)}
                          >
                            <RotateCcw className="h-4 w-4 mr-1" />
                            Restore
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <Pagination className="mt-4">
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    onClick={() => setPage(page - 1)}
                    className={cn(
                      'cursor-pointer select-none',
                      page === 1 && 'pointer-events-none opacity-50'
                    )}
                    aria-disabled={page === 1}
                  />
                </PaginationItem>

                {showStartEllipsis && (
                  <>
                    <PaginationItem>
                      <PaginationLink
                        onClick={() => setPage(1)}
                        className="cursor-pointer select-none"
                      >
                        1
                      </PaginationLink>
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationEllipsis />
                    </PaginationItem>
                  </>
                )}

                {pageRange.map((pageNum) => (
                  <PaginationItem key={pageNum}>
                    <PaginationLink
                      isActive={pageNum === page}
                      onClick={() => setPage(pageNum)}
                      className={cn(
                        'cursor-pointer select-none',
                        pageNum === page &&
                          'bg-linq-blue text-white border-linq-blue hover:bg-linq-blue/90 hover:text-white'
                      )}
                    >
                      {pageNum}
                    </PaginationLink>
                  </PaginationItem>
                ))}

                {showEndEllipsis && (
                  <>
                    <PaginationItem>
                      <PaginationEllipsis />
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationLink
                        onClick={() => setPage(totalPages)}
                        className="cursor-pointer select-none"
                      >
                        {totalPages}
                      </PaginationLink>
                    </PaginationItem>
                  </>
                )}

                <PaginationItem>
                  <PaginationNext
                    onClick={() => setPage(page + 1)}
                    className={cn(
                      'cursor-pointer select-none',
                      page === totalPages && 'pointer-events-none opacity-50'
                    )}
                    aria-disabled={page === totalPages}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          )}
        </>
      )}

      {/* Restore Confirmation Dialog */}
      <Dialog open={showRestoreDialog} onOpenChange={setShowRestoreDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore Service</DialogTitle>
            <DialogDescription>
              Are you sure you want to restore{' '}
              <strong>{selectedSnapshot?.snapshot_data.service_name}</strong> to its state from{' '}
              {selectedSnapshot ? formatDate(selectedSnapshot.created_at) : ''}?
            </DialogDescription>
          </DialogHeader>
          {selectedSnapshot && (
            <div className="py-4">
              <p className="text-sm text-muted-foreground mb-2">
                This will restore the following state:
              </p>
              <dl className="text-sm space-y-1 bg-muted p-3 rounded-lg">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Service Name:</dt>
                  <dd>{selectedSnapshot.snapshot_data.service_name}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Active:</dt>
                  <dd>{selectedSnapshot.snapshot_data.active === 1 ? 'Yes' : 'No'}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Muted:</dt>
                  <dd>{selectedSnapshot.snapshot_data.muted === 1 ? 'Yes' : 'No'}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Priority:</dt>
                  <dd>{selectedSnapshot.snapshot_data.priority.toUpperCase()}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Team:</dt>
                  <dd>{selectedSnapshot.snapshot_data.team || '—'}</dd>
                </div>
              </dl>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowRestoreDialog(false)}
              disabled={isRestoring}
            >
              Cancel
            </Button>
            <Button onClick={handleRestoreConfirm} disabled={isRestoring}>
              {isRestoring ? 'Restoring...' : 'Restore'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
