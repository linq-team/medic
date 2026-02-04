import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createApiClient, ApiError, apiClient } from './api'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('ApiError', () => {
  it('creates an error with correct properties', () => {
    const error = new ApiError('Test error', 404)

    expect(error).toBeInstanceOf(Error)
    expect(error.name).toBe('ApiError')
    expect(error.message).toBe('Test error')
    expect(error.status).toBe(404)
  })

  it('creates an error with response object', () => {
    const response = { success: false, message: 'Not found', results: null }
    const error = new ApiError('Test error', 404, response)

    expect(error.response).toEqual(response)
  })
})

describe('createApiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('configuration', () => {
    it('uses default baseUrl of /api', async () => {
      const client = createApiClient({ apiKey: 'test-key' })

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getServices()

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/service',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-key',
          }),
        })
      )
    })

    it('uses custom baseUrl when provided', async () => {
      const client = createApiClient({
        baseUrl: 'https://api.example.com',
        apiKey: 'test-key',
      })

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getServices()

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/service',
        expect.anything()
      )
    })
  })

  describe('setApiKey', () => {
    it('updates the API key used in requests', async () => {
      const client = createApiClient({ apiKey: 'initial-key' })

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getServices()
      expect(mockFetch).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer initial-key',
          }),
        })
      )

      client.setApiKey('new-key')
      await client.getServices()

      expect(mockFetch).toHaveBeenLastCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer new-key',
          }),
        })
      )
    })
  })

  describe('hasApiKey', () => {
    it('returns false when no API key is set', () => {
      const client = createApiClient()
      expect(client.hasApiKey()).toBe(false)
    })

    it('returns true when API key is set', () => {
      const client = createApiClient({ apiKey: 'test-key' })
      expect(client.hasApiKey()).toBe(true)
    })

    it('returns true after setApiKey is called', () => {
      const client = createApiClient()
      expect(client.hasApiKey()).toBe(false)

      client.setApiKey('test-key')
      expect(client.hasApiKey()).toBe(true)
    })
  })

  describe('authenticated requests', () => {
    it('throws ApiError when API key is not configured', async () => {
      const client = createApiClient()

      await expect(client.getServices()).rejects.toThrow(ApiError)
      await expect(client.getServices()).rejects.toMatchObject({
        status: 401,
        message: 'API key not configured',
      })
    })

    it('includes Authorization header with Bearer token', async () => {
      const client = createApiClient({ apiKey: 'test-api-key' })

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getServices()

      expect(mockFetch).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-api-key',
            'Content-Type': 'application/json',
          }),
        })
      )
    })
  })

  describe('error handling', () => {
    const client = createApiClient({ apiKey: 'test-key' })

    it('throws ApiError with status 401 for unauthorized response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ message: 'Unauthorized' }),
      })

      await expect(client.getServices()).rejects.toMatchObject({
        status: 401,
        message: 'Unauthorized: Invalid or missing API key',
      })
    })

    it('throws ApiError with status 403 for forbidden response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ message: 'Forbidden' }),
      })

      await expect(client.getServices()).rejects.toMatchObject({
        status: 403,
        message: 'Forbidden: Insufficient permissions',
      })
    })

    it('throws ApiError with status 404 for not found response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ message: 'Not found' }),
      })

      await expect(client.getServices()).rejects.toMatchObject({
        status: 404,
        message: 'Not found: Resource does not exist',
      })
    })

    it('throws ApiError with status 429 for rate limit response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: () => Promise.resolve({ message: 'Too many requests' }),
      })

      await expect(client.getServices()).rejects.toMatchObject({
        status: 429,
        message: 'Rate limit exceeded',
      })
    })

    it('throws ApiError with status 500 for server error response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ message: 'Internal error' }),
      })

      await expect(client.getServices()).rejects.toMatchObject({
        status: 500,
        message: 'Internal server error',
      })
    })

    it('throws ApiError with status 503 for service unavailable response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: () => Promise.resolve({ message: 'Service unavailable' }),
      })

      await expect(client.getServices()).rejects.toMatchObject({
        status: 503,
        message: 'Service unavailable',
      })
    })

    it('handles non-JSON error responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      })

      await expect(client.getServices()).rejects.toMatchObject({
        status: 500,
      })
    })
  })

  describe('health endpoints (unauthenticated)', () => {
    it('getHealth does not require API key', async () => {
      const client = createApiClient() // No API key

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: 'healthy' }),
      })

      const result = await client.getHealth()

      expect(result).toEqual({ status: 'healthy' })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/health',
        expect.objectContaining({
          headers: expect.not.objectContaining({
            Authorization: expect.anything(),
          }),
        })
      )
    })

    it('getLiveness does not require API key', async () => {
      const client = createApiClient()

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: 'healthy' }),
      })

      await client.getLiveness()

      expect(mockFetch).toHaveBeenCalledWith('/api/health/live', expect.anything())
    })

    it('getReadiness does not require API key', async () => {
      const client = createApiClient()

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: 'ready' }),
      })

      await client.getReadiness()

      expect(mockFetch).toHaveBeenCalledWith('/api/health/ready', expect.anything())
    })
  })

  describe('service endpoints', () => {
    const client = createApiClient({ apiKey: 'test-key' })

    it('getServices fetches all services', async () => {
      const services = [
        { service_id: 1, heartbeat_name: 'service-1', service_name: 'Service 1' },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: services }),
      })

      const result = await client.getServices()

      expect(result.results).toEqual(services)
      expect(mockFetch).toHaveBeenCalledWith('/api/service', expect.anything())
    })

    it('getServices includes query params when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getServices({ service_name: 'test', active: 1 })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/service?service_name=test&active=1',
        expect.anything()
      )
    })

    it('getServiceByHeartbeatName encodes the heartbeat name', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getServiceByHeartbeatName('service/with/slashes')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/service/service%2Fwith%2Fslashes',
        expect.anything()
      )
    })

    it('createService sends POST request with service data', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: 'Created', results: '' }),
      })

      await client.createService({
        heartbeat_name: 'new-service',
        service_name: 'New Service',
        alert_interval: 60,
        team: 'platform',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/service',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            heartbeat_name: 'new-service',
            service_name: 'New Service',
            alert_interval: 60,
            team: 'platform',
          }),
        })
      )
    })

    it('updateService sends POST request with updates', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: 'Updated', results: '' }),
      })

      await client.updateService('my-service', { muted: 1 })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/service/my-service',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ muted: 1 }),
        })
      )
    })
  })

  describe('alert endpoints', () => {
    const client = createApiClient({ apiKey: 'test-key' })

    it('getAlerts fetches all alerts', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getAlerts()

      expect(mockFetch).toHaveBeenCalledWith('/api/alerts', expect.anything())
    })

    it('getAlerts includes active filter when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getAlerts({ active: 1 })

      expect(mockFetch).toHaveBeenCalledWith('/api/alerts?active=1', expect.anything())
    })
  })

  describe('playbook endpoints', () => {
    const client = createApiClient({ apiKey: 'test-key' })

    it('getPlaybooks fetches all playbooks', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getPlaybooks()

      expect(mockFetch).toHaveBeenCalledWith('/api/v2/playbooks', expect.anything())
    })

    it('getPlaybooks includes filters when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: '', results: [] }),
      })

      await client.getPlaybooks({ active: 1, trigger_type: 'alert' })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v2/playbooks?active=1&trigger_type=alert',
        expect.anything()
      )
    })

    it('executePlaybook sends POST request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: '',
            results: { execution_id: 1, playbook_id: 1, playbook_name: 'test', status: 'running' },
          }),
      })

      await client.executePlaybook(1, { service_id: 5 })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v2/playbooks/1/execute',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ service_id: 5 }),
        })
      )
    })
  })

  describe('audit log endpoints', () => {
    const client = createApiClient({ apiKey: 'test-key' })

    it('getAuditLogs fetches audit logs with pagination', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: '',
            results: { entries: [], total_count: 0, limit: 25, offset: 0, has_more: false },
          }),
      })

      await client.getAuditLogs({ limit: 25, offset: 50 })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v2/audit-logs?limit=25&offset=50',
        expect.anything()
      )
    })

    it('getAuditLogs includes filters when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: '',
            results: { entries: [], total_count: 0, limit: 25, offset: 0, has_more: false },
          }),
      })

      await client.getAuditLogs({
        action_type: 'execution_started',
        actor: 'admin',
        start_date: '2026-01-01',
        end_date: '2026-01-31',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v2/audit-logs?action_type=execution_started&actor=admin&start_date=2026-01-01&end_date=2026-01-31',
        expect.anything()
      )
    })
  })
})

describe('apiClient (default instance)', () => {
  it('is a pre-configured API client instance', () => {
    expect(apiClient).toBeDefined()
    expect(typeof apiClient.getServices).toBe('function')
    expect(typeof apiClient.setApiKey).toBe('function')
    expect(typeof apiClient.hasApiKey).toBe('function')
  })
})
