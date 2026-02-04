import { Server, Activity, AlertTriangle, Bell } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useServices, useAlerts } from '@/hooks'
import { cn } from '@/lib/utils'

/**
 * Summary card component for displaying a metric with icon
 */
interface SummaryCardProps {
  title: string
  value: number | string
  icon: React.ReactNode
  description?: string
  colorClass?: string
  isLoading?: boolean
}

function SummaryCard({
  title,
  value,
  icon,
  description,
  colorClass = 'text-foreground',
  isLoading = false,
}: SummaryCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <div className="text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <>
            <Skeleton className="h-8 w-16 mb-1" />
            <Skeleton className="h-4 w-24" />
          </>
        ) : (
          <>
            <div className={cn('text-3xl font-bold font-mono', colorClass)}>
              {value}
            </div>
            {description && (
              <p className="text-xs text-muted-foreground mt-1">{description}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Dashboard page with service health summary cards
 */
export function Dashboard() {
  const {
    data: servicesData,
    isLoading: isLoadingServices,
    error: servicesError,
  } = useServices()

  const {
    data: alertsData,
    isLoading: isLoadingAlerts,
    error: alertsError,
  } = useAlerts({ active: 1 })

  const services = servicesData?.results ?? []
  const activeAlerts = alertsData?.results ?? []

  // Calculate summary metrics
  const totalServices = services.length
  const activeServices = services.filter((s) => s.active === 1).length
  const downServices = services.filter((s) => s.down === 1).length
  const activeAlertCount = activeAlerts.length

  const isLoading = isLoadingServices || isLoadingAlerts
  const hasError = servicesError || alertsError

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Service health overview and alerts summary
      </p>

      {hasError && (
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Error loading data</span>
          </div>
          <p className="mt-1 text-sm">
            {servicesError?.message || alertsError?.message || 'Failed to fetch data from the API'}
          </p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Total Services"
          value={totalServices}
          icon={<Server className="h-4 w-4" />}
          description="Registered services"
          isLoading={isLoading}
        />

        <SummaryCard
          title="Active Services"
          value={activeServices}
          icon={<Activity className="h-4 w-4" />}
          description="Currently monitored"
          colorClass="text-status-healthy"
          isLoading={isLoading}
        />

        <SummaryCard
          title="Down Services"
          value={downServices}
          icon={<AlertTriangle className="h-4 w-4" />}
          description={downServices > 0 ? 'Requires attention' : 'All services healthy'}
          colorClass={downServices > 0 ? 'text-status-error' : 'text-status-healthy'}
          isLoading={isLoading}
        />

        <SummaryCard
          title="Active Alerts"
          value={activeAlertCount}
          icon={<Bell className="h-4 w-4" />}
          description={activeAlertCount > 0 ? 'Unresolved alerts' : 'No active alerts'}
          colorClass={activeAlertCount > 0 ? 'text-status-error' : 'text-status-healthy'}
          isLoading={isLoading}
        />
      </div>
    </div>
  )
}
