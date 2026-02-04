import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  AlertTriangle,
  Bell,
  Clock,
  Calendar,
  Users,
  ExternalLink,
  CheckCircle,
  Server,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAlerts } from '@/hooks'
import { cn } from '@/lib/utils'
import type { Alert } from '@/lib/api'

/**
 * Format a date string to a human-readable format
 */
function formatDate(dateString: string | null): string {
  if (!dateString) return '—'
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format a date string to relative time (e.g., "2 hours ago")
 */
function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return ''

  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) {
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
  }
  if (diffHours > 0) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  }
  if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`
  }
  return 'just now'
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
    return `${hours}h ${minutes}m ${secs}s`
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`
  }
  return `${secs}s`
}

/**
 * Get status badge props for an alert
 */
function getStatusBadge(alert: Alert): {
  variant: 'default' | 'secondary' | 'destructive' | 'outline'
  label: string
  icon: typeof Bell
} {
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
      return { className: 'bg-status-error text-white', label: 'P1 - Critical' }
    case 'p2':
      return { className: 'bg-status-warning text-black dark:text-white', label: 'P2 - High' }
    case 'p3':
      return { className: 'bg-muted text-muted-foreground', label: 'P3 - Normal' }
    default:
      return { className: 'bg-muted text-muted-foreground', label: priority.toUpperCase() }
  }
}

/**
 * Loading skeleton for the alert detail page
 */
function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-8 w-64" />
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-5 w-1/2" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-5 w-1/2" />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

/**
 * Not found state when alert doesn't exist
 */
function NotFoundState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Bell className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium text-foreground mb-2">Alert not found</h3>
      <p className="text-muted-foreground max-w-sm mb-6">
        The alert you're looking for doesn't exist or may have been removed.
      </p>
      <Link to="/alerts">
        <Button variant="outline">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Alerts
        </Button>
      </Link>
    </div>
  )
}

/**
 * Detail row component for consistent styling
 */
function DetailRow({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4 py-2 border-b last:border-0">
      <dt className="text-sm font-medium text-muted-foreground w-32 shrink-0">
        {label}
      </dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  )
}

/**
 * Alert detail page component
 *
 * Displays detailed information about a specific alert
 */
export function AlertDetail() {
  const { id } = useParams<{ id: string }>()
  const alertId = id ? parseInt(id, 10) : NaN
  const { data, isLoading, error } = useAlerts()

  // Find the alert by ID from the list
  const alert = data?.results?.find((a) => a.alert_id === alertId)

  if (isLoading) {
    return (
      <div className="p-8">
        <DetailSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Error loading alert</span>
          </div>
          <p className="mt-1 text-sm">{error.message || 'Failed to fetch alert from the API'}</p>
        </div>
        <Link to="/alerts">
          <Button variant="outline">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Alerts
          </Button>
        </Link>
      </div>
    )
  }

  if (!alert || isNaN(alertId)) {
    return (
      <div className="p-8">
        <NotFoundState />
      </div>
    )
  }

  const statusBadge = getStatusBadge(alert)
  const priorityBadge = getPriorityBadge(alert.priority)
  const StatusIcon = statusBadge.icon

  return (
    <div className="p-8">
      {/* Header with back button */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-6">
        <Link to="/alerts">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-foreground">{alert.heartbeat_name}</h1>
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
          <Badge className={priorityBadge.className}>{priorityBadge.label}</Badge>
        </div>
      </div>

      {/* Main content grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Alert Information Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-linq-blue" />
              Alert Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-1">
              <DetailRow label="Alert ID">
                <code className="px-2 py-1 bg-muted rounded text-sm font-mono">
                  {alert.alert_id}
                </code>
              </DetailRow>
              <DetailRow label="Heartbeat Name">
                <code className="px-2 py-1 bg-muted rounded text-sm font-mono">
                  {alert.heartbeat_name}
                </code>
              </DetailRow>
              <DetailRow label="Service">
                <Link
                  to={`/services/${encodeURIComponent(alert.heartbeat_name)}`}
                  className="inline-flex items-center gap-1 text-linq-blue hover:underline"
                >
                  <Server className="h-4 w-4" />
                  {alert.service_name}
                </Link>
              </DetailRow>
              <DetailRow label="Team">
                <span className="inline-flex items-center gap-1">
                  <Users className="h-4 w-4 text-muted-foreground" />
                  {alert.team || '—'}
                </span>
              </DetailRow>
              <DetailRow label="Priority">
                <Badge className={priorityBadge.className}>{priorityBadge.label}</Badge>
              </DetailRow>
              <DetailRow label="Status">
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
              </DetailRow>
            </dl>
          </CardContent>
        </Card>

        {/* Timestamps Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-linq-blue" />
              Timeline
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-1">
              <DetailRow label="Created">
                <span className="flex flex-col">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    {formatDate(alert.created_date)}
                  </span>
                  {alert.created_date && (
                    <span className="text-xs text-muted-foreground mt-1">
                      {formatRelativeTime(alert.created_date)}
                    </span>
                  )}
                </span>
              </DetailRow>
              <DetailRow label="Closed">
                <span className="flex flex-col">
                  <span className="inline-flex items-center gap-1">
                    {alert.closed_date ? (
                      <>
                        <CheckCircle className="h-4 w-4 text-status-healthy" />
                        {formatDate(alert.closed_date)}
                      </>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </span>
                  {alert.closed_date && (
                    <span className="text-xs text-muted-foreground mt-1">
                      {formatRelativeTime(alert.closed_date)}
                    </span>
                  )}
                </span>
              </DetailRow>
              <DetailRow label="Duration">
                <span className="font-mono">
                  {alert.active === 1 ? (
                    <span className="text-status-error">Ongoing</span>
                  ) : (
                    formatDuration(alert.duration)
                  )}
                </span>
              </DetailRow>
            </dl>
          </CardContent>
        </Card>

        {/* Runbook Card (only if runbook exists) */}
        {alert.runbook && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ExternalLink className="h-5 w-5 text-linq-blue" />
                Runbook
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-3">
                Follow the runbook for troubleshooting and resolution steps.
              </p>
              <a
                href={alert.runbook}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-linq-blue hover:underline"
              >
                {alert.runbook}
                <ExternalLink className="h-4 w-4" />
              </a>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
