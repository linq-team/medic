import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  AlertTriangle,
  Server,
  Clock,
  Calendar,
  Users,
  ExternalLink,
  Eye,
  EyeOff,
  Pencil,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ServiceEditModal } from '@/components/service-edit-modal'
import { useService } from '@/hooks'
import { cn } from '@/lib/utils'
import type { Service } from '@/lib/api'

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
 * Format alert interval (in minutes) to human-readable format
 */
function formatAlertInterval(minutes: number): string {
  if (minutes < 60) {
    return `${minutes} minute${minutes !== 1 ? 's' : ''}`
  }
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  if (remainingMinutes === 0) {
    return `${hours} hour${hours !== 1 ? 's' : ''}`
  }
  return `${hours}h ${remainingMinutes}m`
}

/**
 * Get status badge props for a service
 */
function getStatusBadge(service: Service): {
  variant: 'default' | 'secondary' | 'destructive' | 'outline'
  label: string
} {
  if (service.active === 0) {
    return { variant: 'secondary', label: 'Inactive' }
  }
  return { variant: 'default', label: 'Active' }
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
 * Loading skeleton for the service detail page
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
 * Not found state when service doesn't exist
 */
function NotFoundState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Server className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium text-foreground mb-2">Service not found</h3>
      <p className="text-muted-foreground max-w-sm mb-6">
        The service you're looking for doesn't exist or may have been removed.
      </p>
      <Link to="/services">
        <Button variant="outline">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Services
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
 * Service detail page component
 *
 * Displays detailed information about a specific service
 */
export function ServiceDetail() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, error } = useService(id ?? '')
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)

  // The API returns an array, get the first (and usually only) result
  const service = data?.results?.[0]

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
            <span className="font-medium">Error loading service</span>
          </div>
          <p className="mt-1 text-sm">{error.message || 'Failed to fetch service from the API'}</p>
        </div>
        <Link to="/services">
          <Button variant="outline">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Services
          </Button>
        </Link>
      </div>
    )
  }

  if (!service) {
    return (
      <div className="p-8">
        <NotFoundState />
      </div>
    )
  }

  const statusBadge = getStatusBadge(service)
  const priorityBadge = getPriorityBadge(service.priority)

  return (
    <div className="p-8">
      {/* Header with back button and edit button */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-6">
        <div className="flex items-center gap-2">
          <Link to="/services">
            <Button variant="outline" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={() => setIsEditModalOpen(true)}>
            <Pencil className="h-4 w-4 mr-2" />
            Edit
          </Button>
        </div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-foreground">{service.service_name}</h1>
          <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
          {service.down === 1 && (
            <Badge variant="destructive" className="animate-pulse">
              <AlertTriangle className="h-3 w-3 mr-1" />
              Down
            </Badge>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      <ServiceEditModal
        service={service}
        open={isEditModalOpen}
        onOpenChange={setIsEditModalOpen}
      />

      {/* Main content grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Service Information Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-linq-blue" />
              Service Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-1">
              <DetailRow label="Heartbeat Name">
                <code className="px-2 py-1 bg-muted rounded text-sm font-mono">
                  {service.heartbeat_name}
                </code>
              </DetailRow>
              <DetailRow label="Service Name">{service.service_name}</DetailRow>
              <DetailRow label="Team">
                <span className="inline-flex items-center gap-1">
                  <Users className="h-4 w-4 text-muted-foreground" />
                  {service.team || '—'}
                </span>
              </DetailRow>
              <DetailRow label="Priority">
                <Badge className={priorityBadge.className}>{priorityBadge.label}</Badge>
              </DetailRow>
              <DetailRow label="Status">
                <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
              </DetailRow>
            </dl>
          </CardContent>
        </Card>

        {/* Monitoring Configuration Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-linq-blue" />
              Monitoring Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-1">
              <DetailRow label="Alert Interval">
                {formatAlertInterval(service.alert_interval)}
              </DetailRow>
              <DetailRow label="Threshold">{service.threshold} missed heartbeats</DetailRow>
              <DetailRow label="Down">
                <span
                  className={cn(
                    'inline-flex items-center gap-1 font-medium',
                    service.down === 1 ? 'text-status-error' : 'text-status-healthy'
                  )}
                >
                  {service.down === 1 ? (
                    <>
                      <AlertTriangle className="h-4 w-4" />
                      Yes
                    </>
                  ) : (
                    'No'
                  )}
                </span>
              </DetailRow>
              <DetailRow label="Muted">
                <span
                  className={cn(
                    'inline-flex items-center gap-1',
                    service.muted === 1 ? 'text-muted-foreground' : 'text-foreground'
                  )}
                >
                  {service.muted === 1 ? (
                    <>
                      <EyeOff className="h-4 w-4" />
                      Yes
                    </>
                  ) : (
                    <>
                      <Eye className="h-4 w-4" />
                      No
                    </>
                  )}
                </span>
              </DetailRow>
            </dl>
          </CardContent>
        </Card>

        {/* Runbook Card (only if runbook exists) */}
        {service.runbook && (
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ExternalLink className="h-5 w-5 text-linq-blue" />
                Runbook
              </CardTitle>
            </CardHeader>
            <CardContent>
              <a
                href={service.runbook}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-linq-blue hover:underline"
              >
                {service.runbook}
                <ExternalLink className="h-4 w-4" />
              </a>
            </CardContent>
          </Card>
        )}

        {/* Timestamps Card */}
        <Card className={service.runbook ? '' : 'md:col-span-2'}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-linq-blue" />
              Timestamps
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-1">
              <DetailRow label="Date Added">{formatDate(service.date_added)}</DetailRow>
              <DetailRow label="Last Modified">{formatDate(service.date_modified)}</DetailRow>
              <DetailRow label="Date Muted">{formatDate(service.date_muted)}</DetailRow>
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
