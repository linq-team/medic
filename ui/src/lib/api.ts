/**
 * Medic API Client Module
 *
 * Provides a fetch-based API client with TypeScript types for communicating
 * with the Medic backend API.
 */

// ============================================================================
// TypeScript Types
// ============================================================================

/**
 * Service entity representing a monitored heartbeat/service
 */
export interface Service {
  service_id: number
  heartbeat_name: string
  service_name: string
  active: number // 0 or 1
  alert_interval: number
  threshold: number
  team: string
  priority: string // p1, p2, p3
  muted: number // 0 or 1
  down: number // 0 or 1
  runbook: string | null
  date_added: string
  date_modified: string | null
  date_muted: string | null
}

/**
 * Alert entity representing an active or historical alert
 */
export interface Alert {
  alert_id: number
  service_id: number
  heartbeat_name: string
  service_name: string
  active: number // 0 or 1
  priority: string
  team: string
  created_date: string
  closed_date: string | null
  duration: number | null // in seconds
  runbook: string | null
}

/**
 * Heartbeat event entity representing a single heartbeat ping
 */
export interface Heartbeat {
  heartbeat_id: number
  heartbeat_name: string
  service_name: string
  time: string
  status: HeartbeatStatus
  team: string
  priority: string
  run_id?: string | null
}

/**
 * Valid heartbeat status values
 */
export type HeartbeatStatus = 'UP' | 'DOWN' | 'STARTED' | 'COMPLETED' | 'FAILED'

/**
 * Audit log entry for playbook executions
 */
export interface AuditLogEntry {
  log_id: number
  execution_id: number
  action_type: AuditActionType
  details: Record<string, unknown>
  actor: string | null
  timestamp: string
  created_at: string | null
}

/**
 * Valid audit action types
 */
export type AuditActionType =
  | 'execution_started'
  | 'step_completed'
  | 'step_failed'
  | 'approval_requested'
  | 'approved'
  | 'rejected'
  | 'execution_completed'
  | 'execution_failed'

/**
 * Playbook entity
 */
export interface Playbook {
  playbook_id: number
  name: string
  description: string | null
  trigger_type: string
  active: number // 0 or 1
  last_run: string | null
  status: PlaybookStatus | null
}

/**
 * Valid playbook execution statuses
 */
export type PlaybookStatus =
  | 'pending_approval'
  | 'running'
  | 'waiting'
  | 'completed'
  | 'failed'
  | 'cancelled'

/**
 * Valid snapshot action types
 */
export type SnapshotActionType =
  | 'deactivate'
  | 'activate'
  | 'mute'
  | 'unmute'
  | 'edit'
  | 'bulk_edit'
  | 'priority_change'
  | 'team_change'
  | 'delete'

/**
 * Snapshot data representing the captured service state
 */
export interface SnapshotData {
  service_id: number
  heartbeat_name: string
  service_name: string
  active: number
  alert_interval: number
  threshold: number
  team: string
  priority: string
  muted: number
  down: number
  runbook: string | null
  date_added: string
  date_modified: string | null
  date_muted: string | null
}

/**
 * Service snapshot representing a point-in-time backup of service state
 */
export interface Snapshot {
  snapshot_id: number
  service_id: number
  snapshot_data: SnapshotData
  action_type: SnapshotActionType
  actor: string | null
  created_at: string
  restored_at: string | null
}

/**
 * Standard API response envelope
 */
export interface ApiResponse<T> {
  success: boolean
  message: string
  results: T
}

/**
 * Paginated response wrapper
 */
export interface PaginatedResponse<T> {
  entries: T[]
  total_count: number
  limit: number
  offset: number
  has_more: boolean
}

/**
 * Health status response
 */
export interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'ready' | 'not_ready'
  checks?: Record<string, { status: string; message?: string }>
  timestamp?: string
}

// ============================================================================
// Error Types
// ============================================================================

/**
 * Custom error class for API errors with status code
 */
export class ApiError extends Error {
  status: number
  response?: ApiResponse<unknown>

  constructor(message: string, status: number, response?: ApiResponse<unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.response = response
  }
}

// ============================================================================
// API Client
// ============================================================================

/**
 * Configuration for the API client
 */
export interface ApiClientConfig {
  baseUrl?: string
  apiKey?: string
}

/**
 * Creates an API client instance with the given configuration.
 *
 * @param config - Configuration options
 * @returns API client object with methods for each endpoint
 */
export function createApiClient(config: ApiClientConfig = {}) {
  const baseUrl = config.baseUrl || '/api'

  /**
   * Get the API key from config or throw if not available
   */
  function getApiKey(): string {
    if (!config.apiKey) {
      throw new ApiError('API key not configured', 401)
    }
    return config.apiKey
  }

  /**
   * Make an authenticated fetch request to the API
   */
  async function fetchWithAuth<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${baseUrl}${endpoint}`

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getApiKey()}`,
      ...options.headers,
    }

    const response = await fetch(url, {
      ...options,
      headers,
    })

    // Handle common error responses
    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`
      let errorResponse: ApiResponse<unknown> | undefined

      try {
        errorResponse = await response.json()
        errorMessage = errorResponse?.message || errorMessage
      } catch {
        // Response body is not JSON
      }

      switch (response.status) {
        case 401:
          throw new ApiError('Unauthorized: Invalid or missing API key', 401, errorResponse)
        case 403:
          throw new ApiError('Forbidden: Insufficient permissions', 403, errorResponse)
        case 404:
          throw new ApiError('Not found: Resource does not exist', 404, errorResponse)
        case 429:
          throw new ApiError('Rate limit exceeded', 429, errorResponse)
        case 500:
          throw new ApiError('Internal server error', 500, errorResponse)
        case 503:
          throw new ApiError('Service unavailable', 503, errorResponse)
        default:
          throw new ApiError(errorMessage, response.status, errorResponse)
      }
    }

    return response.json()
  }

  /**
   * Make an unauthenticated fetch request (for health checks)
   */
  async function fetchWithoutAuth<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${baseUrl}${endpoint}`

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (!response.ok) {
      throw new ApiError(`HTTP ${response.status}`, response.status)
    }

    return response.json()
  }

  return {
    /**
     * Update the API key
     */
    setApiKey(apiKey: string) {
      config.apiKey = apiKey
    },

    /**
     * Check if API key is configured
     */
    hasApiKey(): boolean {
      return !!config.apiKey
    },

    // =========================================================================
    // Health Endpoints
    // =========================================================================

    /**
     * Get full health status (no auth required)
     */
    async getHealth(): Promise<HealthStatus> {
      return fetchWithoutAuth<HealthStatus>('/health')
    },

    /**
     * Get liveness probe status (no auth required)
     */
    async getLiveness(): Promise<HealthStatus> {
      return fetchWithoutAuth<HealthStatus>('/health/live')
    },

    /**
     * Get readiness probe status (no auth required)
     */
    async getReadiness(): Promise<HealthStatus> {
      return fetchWithoutAuth<HealthStatus>('/health/ready')
    },

    // =========================================================================
    // Service Endpoints
    // =========================================================================

    /**
     * Get all services with optional filters
     */
    async getServices(params?: {
      service_name?: string
      active?: number
    }): Promise<ApiResponse<Service[]>> {
      const searchParams = new URLSearchParams()
      if (params?.service_name) searchParams.set('service_name', params.service_name)
      if (params?.active !== undefined) searchParams.set('active', String(params.active))

      const query = searchParams.toString()
      const endpoint = query ? `/service?${query}` : '/service'

      return fetchWithAuth<ApiResponse<Service[]>>(endpoint)
    },

    /**
     * Get a single service by heartbeat name
     */
    async getServiceByHeartbeatName(heartbeatName: string): Promise<ApiResponse<Service[]>> {
      return fetchWithAuth<ApiResponse<Service[]>>(`/service/${encodeURIComponent(heartbeatName)}`)
    },

    /**
     * Create a new service
     */
    async createService(service: {
      heartbeat_name: string
      service_name: string
      alert_interval: number
      environment?: string
      threshold?: number
      team?: string
      priority?: string
      runbook?: string
    }): Promise<ApiResponse<string>> {
      return fetchWithAuth<ApiResponse<string>>('/service', {
        method: 'POST',
        body: JSON.stringify(service),
      })
    },

    /**
     * Update an existing service
     */
    async updateService(
      heartbeatName: string,
      updates: Partial<{
        service_name: string
        muted: number
        active: number
        alert_interval: number
        threshold: number
        team: string
        priority: string
        runbook: string
        down: number
      }>
    ): Promise<ApiResponse<string>> {
      return fetchWithAuth<ApiResponse<string>>(`/service/${encodeURIComponent(heartbeatName)}`, {
        method: 'POST',
        body: JSON.stringify(updates),
      })
    },

    // =========================================================================
    // Heartbeat Endpoints
    // =========================================================================

    /**
     * Get heartbeat events with optional filters
     */
    async getHeartbeats(params?: {
      heartbeat_name?: string
      service_name?: string
      maxCount?: number
    }): Promise<ApiResponse<Heartbeat[]>> {
      const searchParams = new URLSearchParams()
      if (params?.heartbeat_name) searchParams.set('heartbeat_name', params.heartbeat_name)
      if (params?.service_name) searchParams.set('service_name', params.service_name)
      if (params?.maxCount) searchParams.set('maxCount', String(params.maxCount))

      const query = searchParams.toString()
      const endpoint = query ? `/heartbeat?${query}` : '/heartbeat'

      return fetchWithAuth<ApiResponse<Heartbeat[]>>(endpoint)
    },

    /**
     * Post a heartbeat event
     */
    async postHeartbeat(heartbeat: {
      heartbeat_name: string
      status: HeartbeatStatus
      service_name?: string
    }): Promise<ApiResponse<string>> {
      return fetchWithAuth<ApiResponse<string>>('/heartbeat', {
        method: 'POST',
        body: JSON.stringify(heartbeat),
      })
    },

    // =========================================================================
    // V2 Heartbeat Endpoints (Job Tracking)
    // =========================================================================

    /**
     * Record a job start signal
     */
    async recordJobStart(
      serviceId: number,
      runId?: string
    ): Promise<ApiResponse<{ service_id: number; heartbeat_name: string; status: string; run_id: string | null }>> {
      return fetchWithAuth(`/v2/heartbeat/${serviceId}/start`, {
        method: 'POST',
        body: runId ? JSON.stringify({ run_id: runId }) : undefined,
      })
    },

    /**
     * Record a job completion signal
     */
    async recordJobComplete(
      serviceId: number,
      runId?: string
    ): Promise<ApiResponse<{ service_id: number; heartbeat_name: string; status: string; run_id: string | null; duration_ms?: number }>> {
      return fetchWithAuth(`/v2/heartbeat/${serviceId}/complete`, {
        method: 'POST',
        body: runId ? JSON.stringify({ run_id: runId }) : undefined,
      })
    },

    /**
     * Record a job failure signal
     */
    async recordJobFail(
      serviceId: number,
      runId?: string
    ): Promise<ApiResponse<{ service_id: number; heartbeat_name: string; status: string; run_id: string | null }>> {
      return fetchWithAuth(`/v2/heartbeat/${serviceId}/fail`, {
        method: 'POST',
        body: runId ? JSON.stringify({ run_id: runId }) : undefined,
      })
    },

    /**
     * Get duration statistics for a service
     */
    async getServiceStats(serviceId: number): Promise<ApiResponse<{
      run_count: number
      avg_duration_ms: number | null
      p50_duration_ms: number | null
      p95_duration_ms: number | null
      p99_duration_ms: number | null
    }>> {
      return fetchWithAuth(`/v2/services/${serviceId}/stats`)
    },

    // =========================================================================
    // Alert Endpoints
    // =========================================================================

    /**
     * Get alerts with optional active filter
     */
    async getAlerts(params?: { active?: number }): Promise<ApiResponse<Alert[]>> {
      const searchParams = new URLSearchParams()
      if (params?.active !== undefined) searchParams.set('active', String(params.active))

      const query = searchParams.toString()
      const endpoint = query ? `/alerts?${query}` : '/alerts'

      return fetchWithAuth<ApiResponse<Alert[]>>(endpoint)
    },

    // =========================================================================
    // Audit Log Endpoints
    // =========================================================================

    /**
     * Query audit logs with filters and pagination
     */
    async getAuditLogs(params?: {
      execution_id?: number
      service_id?: number
      action_type?: AuditActionType
      actor?: string
      start_date?: string // ISO format
      end_date?: string // ISO format
      limit?: number
      offset?: number
    }): Promise<ApiResponse<PaginatedResponse<AuditLogEntry>>> {
      const searchParams = new URLSearchParams()
      if (params?.execution_id) searchParams.set('execution_id', String(params.execution_id))
      if (params?.service_id) searchParams.set('service_id', String(params.service_id))
      if (params?.action_type) searchParams.set('action_type', params.action_type)
      if (params?.actor) searchParams.set('actor', params.actor)
      if (params?.start_date) searchParams.set('start_date', params.start_date)
      if (params?.end_date) searchParams.set('end_date', params.end_date)
      if (params?.limit) searchParams.set('limit', String(params.limit))
      if (params?.offset) searchParams.set('offset', String(params.offset))

      const query = searchParams.toString()
      const endpoint = query ? `/v2/audit-logs?${query}` : '/v2/audit-logs'

      return fetchWithAuth<ApiResponse<PaginatedResponse<AuditLogEntry>>>(endpoint)
    },

    // =========================================================================
    // Playbook Endpoints
    // =========================================================================

    /**
     * Get all playbooks with optional filters
     */
    async getPlaybooks(params?: {
      active?: number
      trigger_type?: string
    }): Promise<ApiResponse<Playbook[]>> {
      const searchParams = new URLSearchParams()
      if (params?.active !== undefined) searchParams.set('active', String(params.active))
      if (params?.trigger_type) searchParams.set('trigger_type', params.trigger_type)

      const query = searchParams.toString()
      const endpoint = query ? `/v2/playbooks?${query}` : '/v2/playbooks'

      return fetchWithAuth<ApiResponse<Playbook[]>>(endpoint)
    },

    /**
     * Execute a playbook
     */
    async executePlaybook(
      playbookId: number,
      params?: {
        service_id?: number
        variables?: Record<string, unknown>
      }
    ): Promise<ApiResponse<{
      execution_id: number
      playbook_id: number
      playbook_name: string
      status: PlaybookStatus
      service_id: number | null
      message?: string
    }>> {
      return fetchWithAuth(`/v2/playbooks/${playbookId}/execute`, {
        method: 'POST',
        body: params ? JSON.stringify(params) : undefined,
      })
    },

    // =========================================================================
    // Snapshot Endpoints
    // =========================================================================

    /**
     * Get snapshots with optional filters and pagination
     */
    async getSnapshots(params?: {
      service_id?: number
      action_type?: SnapshotActionType
      start_date?: string // ISO format
      end_date?: string // ISO format
      limit?: number
      offset?: number
    }): Promise<ApiResponse<PaginatedResponse<Snapshot>>> {
      const searchParams = new URLSearchParams()
      if (params?.service_id) searchParams.set('service_id', String(params.service_id))
      if (params?.action_type) searchParams.set('action_type', params.action_type)
      if (params?.start_date) searchParams.set('start_date', params.start_date)
      if (params?.end_date) searchParams.set('end_date', params.end_date)
      if (params?.limit) searchParams.set('limit', String(params.limit))
      if (params?.offset) searchParams.set('offset', String(params.offset))

      const query = searchParams.toString()
      const endpoint = query ? `/v2/snapshots?${query}` : '/v2/snapshots'

      return fetchWithAuth<ApiResponse<PaginatedResponse<Snapshot>>>(endpoint)
    },

    /**
     * Get a single snapshot by ID
     */
    async getSnapshotById(snapshotId: number): Promise<ApiResponse<Snapshot>> {
      return fetchWithAuth<ApiResponse<Snapshot>>(`/v2/snapshots/${snapshotId}`)
    },

    /**
     * Restore a service from a snapshot
     */
    async restoreSnapshot(
      snapshotId: number,
      params?: { actor?: string }
    ): Promise<ApiResponse<Snapshot>> {
      return fetchWithAuth<ApiResponse<Snapshot>>(`/v2/snapshots/${snapshotId}/restore`, {
        method: 'POST',
        body: params ? JSON.stringify(params) : undefined,
      })
    },
  }
}

/**
 * Default API client instance
 * Use this for simple cases, or create a custom client with createApiClient()
 */
export const apiClient = createApiClient()
