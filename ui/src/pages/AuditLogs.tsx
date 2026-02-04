import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, ScrollText, Clock, User, Hash, Calendar, X } from 'lucide-react'
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
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { useAuditLogs, type AuditLogFilters } from '@/hooks'
import { cn } from '@/lib/utils'
import type { AuditActionType, AuditLogEntry } from '@/lib/api'

/**
 * Available action types for filtering
 */
const ACTION_TYPES: { value: AuditActionType | 'all'; label: string }[] = [
  { value: 'all', label: 'All Actions' },
  { value: 'execution_started', label: 'Execution Started' },
  { value: 'step_completed', label: 'Step Completed' },
  { value: 'step_failed', label: 'Step Failed' },
  { value: 'approval_requested', label: 'Approval Requested' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'execution_completed', label: 'Execution Completed' },
  { value: 'execution_failed', label: 'Execution Failed' },
]

/**
 * Get badge styling for action types
 */
function getActionBadge(actionType: AuditActionType): { className: string; label: string } {
  switch (actionType) {
    case 'execution_started':
      return { className: 'bg-linq-blue/20 text-linq-blue', label: 'Execution Started' }
    case 'step_completed':
      return { className: 'bg-status-healthy/20 text-status-healthy', label: 'Step Completed' }
    case 'step_failed':
      return { className: 'bg-status-error/20 text-status-error', label: 'Step Failed' }
    case 'approval_requested':
      return { className: 'bg-status-warning/20 text-status-warning', label: 'Approval Requested' }
    case 'approved':
      return { className: 'bg-status-healthy/20 text-status-healthy', label: 'Approved' }
    case 'rejected':
      return { className: 'bg-status-error/20 text-status-error', label: 'Rejected' }
    case 'execution_completed':
      return { className: 'bg-linq-green/20 text-linq-green', label: 'Execution Completed' }
    case 'execution_failed':
      return { className: 'bg-status-error/20 text-status-error', label: 'Execution Failed' }
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
      second: '2-digit',
    })
  } catch {
    return dateString
  }
}

/**
 * Format details object to a summary string
 */
function formatSummary(details: Record<string, unknown>): string {
  if (!details || Object.keys(details).length === 0) {
    return '—'
  }

  // Try to extract meaningful summary from common detail fields
  const summaryParts: string[] = []

  if (details.step_name) {
    summaryParts.push(`Step: ${details.step_name}`)
  }
  if (details.playbook_name) {
    summaryParts.push(`Playbook: ${details.playbook_name}`)
  }
  if (details.message) {
    summaryParts.push(String(details.message))
  }
  if (details.error) {
    summaryParts.push(`Error: ${details.error}`)
  }
  if (details.result) {
    summaryParts.push(`Result: ${details.result}`)
  }

  if (summaryParts.length > 0) {
    return summaryParts.join(' | ')
  }

  // Fallback: show first few keys
  const keys = Object.keys(details).slice(0, 3)
  return keys.map((key) => `${key}: ${details[key]}`).join(', ')
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
 * Empty state when no audit logs are found
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <ScrollText className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium text-foreground mb-2">No audit logs found</h3>
      <p className="text-muted-foreground max-w-sm">
        There are no audit log entries recorded yet. Audit logs track playbook executions and related events.
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
 * Audit Logs page with table displaying all audit log entries
 */
export function AuditLogs() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Get filter values from URL
  const actionType = searchParams.get('action_type') || ''
  const actor = searchParams.get('actor') || ''
  const startDate = searchParams.get('start_date') || ''
  const endDate = searchParams.get('end_date') || ''
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10))

  // Local state for debounced actor input
  const [actorInput, setActorInput] = useState(actor)

  // Build filters for the API query
  const filters: AuditLogFilters = {
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  }
  if (actionType && actionType !== 'all') {
    filters.action_type = actionType as AuditActionType
  }
  if (actor) {
    filters.actor = actor
  }
  if (startDate) {
    filters.start_date = startDate
  }
  if (endDate) {
    filters.end_date = endDate
  }

  const { data, isLoading, error } = useAuditLogs(filters)

  const auditLogs = data?.results?.entries ?? []
  const totalCount = data?.results?.total_count ?? 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  // Check if any filters are active
  const hasActiveFilters = !!(actionType && actionType !== 'all') || !!actor || !!startDate || !!endDate

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
    setActorInput('')
  }

  /**
   * Handle actor input change with debounce
   */
  const handleActorChange = (value: string) => {
    setActorInput(value)
    // Debounce the URL update
    const timeoutId = setTimeout(() => {
      setFilter('actor', value)
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

  const pageRange = getPageRange(page, totalPages, 5)
  const showStartEllipsis = pageRange[0] > 1
  const showEndEllipsis = pageRange.length > 0 && pageRange[pageRange.length - 1] < totalPages

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Audit Logs</h1>
      <p className="text-muted-foreground mb-8">
        System audit logs and activity history for playbook executions.
      </p>

      {error && (
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Error loading audit logs</span>
          </div>
          <p className="mt-1 text-sm">
            {error.message || 'Failed to fetch audit logs from the API'}
          </p>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 mb-6">
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

        {/* Actor Filter */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">
            Actor
          </label>
          <div className="relative">
            <User className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Filter by actor..."
              value={actorInput}
              onChange={(e) => handleActorChange(e.target.value)}
              className="pl-8 w-[180px]"
            />
          </div>
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
      ) : auditLogs.length === 0 && !hasActiveFilters ? (
        <EmptyState />
      ) : auditLogs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <ScrollText className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">No matching audit logs</h3>
          <p className="text-muted-foreground max-w-sm mb-4">
            No audit logs match your current filters. Try adjusting or clearing them.
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
                  <TableHead className="w-[180px]">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      Timestamp
                    </span>
                  </TableHead>
                  <TableHead>Action Type</TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      <User className="h-4 w-4" />
                      Actor
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      <Hash className="h-4 w-4" />
                      Execution ID
                    </span>
                  </TableHead>
                  <TableHead>Summary</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {auditLogs.map((log: AuditLogEntry) => {
                  const actionBadge = getActionBadge(log.action_type)

                  return (
                    <TableRow key={log.log_id}>
                      <TableCell className="font-mono text-sm">
                        {formatDate(log.timestamp)}
                      </TableCell>
                      <TableCell>
                        <Badge className={actionBadge.className}>
                          {actionBadge.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {log.actor || '—'}
                      </TableCell>
                      <TableCell className="font-mono">
                        {log.execution_id}
                      </TableCell>
                      <TableCell className="text-muted-foreground max-w-md truncate">
                        {formatSummary(log.details)}
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
    </div>
  )
}
