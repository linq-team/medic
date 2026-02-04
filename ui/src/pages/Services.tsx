import { Link } from 'react-router-dom'
import { Server, AlertTriangle, Eye, EyeOff } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { TablePagination, usePagination } from '@/components/table-pagination'
import { SortableTableHead, useSort } from '@/components/table-sort'
import { TableFilters, useFilter, type FilterConfig } from '@/components/table-filter'
import { useServices } from '@/hooks'
import { cn } from '@/lib/utils'
import type { Service } from '@/lib/api'

/** Default number of services to display per page */
const PAGE_SIZE = 25

/**
 * Filter configurations for the Services table
 */
const SERVICE_FILTERS: FilterConfig[] = [
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
    param: 'muted',
    label: 'Muted',
    options: [
      { value: 'all', label: 'All' },
      { value: '1', label: 'Muted' },
      { value: '0', label: 'Not Muted' },
    ],
    placeholder: 'All',
  },
  {
    param: 'down',
    label: 'Health',
    options: [
      { value: 'all', label: 'All' },
      { value: '1', label: 'Down' },
      { value: '0', label: 'Up' },
    ],
    placeholder: 'All',
  },
]

/**
 * Get status badge variant and label for a service
 */
function getStatusBadge(service: Service): { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string } {
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
 * Empty state when no services are found
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Server className="h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium text-foreground mb-2">No services found</h3>
      <p className="text-muted-foreground max-w-sm">
        There are no registered services yet. Services will appear here once they start sending heartbeats.
      </p>
    </div>
  )
}

/**
 * Services list page with table displaying all registered services
 */
export function Services() {
  const { data, isLoading, error } = useServices()
  const { pageSize, offset } = usePagination('page', PAGE_SIZE)
  const { sortColumn, sortDirection, toggleSort, sortItems } = useSort(
    'sort',
    'dir',
    'service_name', // default sort column
    'asc' // default direction
  )
  const {
    filterState,
    setFilter,
    clearFilters,
    hasActiveFilters,
    filterItems,
  } = useFilter(SERVICE_FILTERS)

  const allServices = data?.results ?? []

  // Filter first, then sort, then paginate
  const filteredServices = filterItems(allServices)
  const sortedServices = sortItems(filteredServices)
  const totalItems = sortedServices.length

  // Paginate services client-side
  const services = sortedServices.slice(offset, offset + pageSize)

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Services</h1>
      <p className="text-muted-foreground mb-8">
        View and manage all registered services and their heartbeat status.
      </p>

      {error && (
        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Error loading services</span>
          </div>
          <p className="mt-1 text-sm">
            {error.message || 'Failed to fetch services from the API'}
          </p>
        </div>
      )}

      {/* Filter controls */}
      {!isLoading && allServices.length > 0 && (
        <TableFilters
          filters={SERVICE_FILTERS}
          filterState={filterState}
          onFilterChange={setFilter}
          onClearFilters={clearFilters}
          hasActiveFilters={hasActiveFilters}
        />
      )}

      {isLoading ? (
        <TableSkeleton />
      ) : allServices.length === 0 ? (
        <EmptyState />
      ) : totalItems === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Server className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">No matching services</h3>
          <p className="text-muted-foreground max-w-sm mb-4">
            No services match your current filters. Try adjusting or clearing your filters.
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-linq-blue hover:underline text-sm"
            >
              Clear all filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead
                    columnKey="service_name"
                    sortColumn={sortColumn}
                    sortDirection={sortDirection}
                    onSort={toggleSort}
                  >
                    Service Name
                  </SortableTableHead>
                  <SortableTableHead
                    columnKey="heartbeat_name"
                    sortColumn={sortColumn}
                    sortDirection={sortDirection}
                    onSort={toggleSort}
                  >
                    Heartbeat Name
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
                    columnKey="down"
                    sortColumn={sortColumn}
                    sortDirection={sortDirection}
                    onSort={toggleSort}
                  >
                    Down
                  </SortableTableHead>
                  <SortableTableHead
                    columnKey="muted"
                    sortColumn={sortColumn}
                    sortDirection={sortDirection}
                    onSort={toggleSort}
                  >
                    Muted
                  </SortableTableHead>
                  <SortableTableHead
                    columnKey="team"
                    sortColumn={sortColumn}
                    sortDirection={sortDirection}
                    onSort={toggleSort}
                  >
                    Team
                  </SortableTableHead>
                  <SortableTableHead
                    columnKey="priority"
                    sortColumn={sortColumn}
                    sortDirection={sortDirection}
                    onSort={toggleSort}
                  >
                    Priority
                  </SortableTableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {services.map((service) => {
                  const statusBadge = getStatusBadge(service)
                  const priorityBadge = getPriorityBadge(service.priority)

                  return (
                    <TableRow key={service.service_id}>
                      <TableCell className="font-medium">
                        <Link
                          to={`/services/${service.service_id}`}
                          className="hover:underline hover:text-linq-blue"
                        >
                          {service.service_name}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {service.heartbeat_name}
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusBadge.variant}>
                          {statusBadge.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 text-sm font-medium',
                            service.down === 1
                              ? 'text-status-error'
                              : 'text-status-healthy'
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
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 text-sm',
                            service.muted === 1
                              ? 'text-muted-foreground'
                              : 'text-foreground'
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
                      </TableCell>
                      <TableCell>{service.team || '—'}</TableCell>
                      <TableCell>
                        <Badge className={priorityBadge.className}>
                          {priorityBadge.label}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          {/* Pagination info and controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-4">
            <p className="text-sm text-muted-foreground">
              Showing {offset + 1} to {Math.min(offset + pageSize, totalItems)} of{' '}
              {totalItems} services
            </p>
            <TablePagination totalItems={totalItems} pageSize={PAGE_SIZE} />
          </div>
        </>
      )}
    </div>
  )
}
