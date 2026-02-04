import { Link } from 'react-router-dom'
import { AlertTriangle, Bell, Clock, CheckCircle } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useAlerts } from '@/hooks'
import { cn } from '@/lib/utils'
import type { Alert } from '@/lib/api'

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

  const alerts = data?.results ?? []

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

      {isLoading ? (
        <TableSkeleton />
      ) : alerts.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Alert Name</TableHead>
                <TableHead>Service</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Created Date</TableHead>
                <TableHead>Closed Date</TableHead>
                <TableHead>Duration</TableHead>
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
                      {alert.heartbeat_name}
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
