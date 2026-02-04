/**
 * Tests for service mutation hooks
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { useUpdateService, useCreateService, useBulkUpdateServices } from './use-service-mutations'
import { servicesKeys } from './use-services'
import { apiClient, type Service, type ApiResponse } from '@/lib/api'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      updateService: vi.fn(),
      createService: vi.fn(),
    },
  }
})

// Create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

// Wrapper component with QueryClientProvider
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

// Mock service data
const mockService: Service = {
  service_id: 1,
  heartbeat_name: 'test-service',
  service_name: 'Test Service',
  active: 1,
  alert_interval: 5,
  threshold: 1,
  team: 'platform',
  priority: 'p3',
  muted: 0,
  down: 0,
  runbook: null,
  date_added: '2026-01-01T00:00:00Z',
  date_modified: null,
  date_muted: null,
}

const mockServicesResponse: ApiResponse<Service[]> = {
  success: true,
  message: '',
  results: [mockService],
}

describe('useUpdateService', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('calls apiClient.updateService with correct parameters', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    const { result } = renderHook(() => useUpdateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatName: 'test-service',
      updates: { muted: 1 },
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockUpdateService).toHaveBeenCalledWith('test-service', { muted: 1 })
  })

  it('performs optimistic update on services list', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    // Delay the response to test optimistic update
    mockUpdateService.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ success: true, message: 'Updated', results: '' }), 100))
    )

    // Pre-populate cache with services
    queryClient.setQueryData(servicesKeys.lists(), mockServicesResponse)

    const { result } = renderHook(() => useUpdateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatName: 'test-service',
      updates: { muted: 1 },
    })

    // Check that optimistic update happened immediately
    await waitFor(() => {
      const cachedData = queryClient.getQueryData<ApiResponse<Service[]>>(servicesKeys.lists())
      expect(cachedData?.results[0].muted).toBe(1)
    })
  })

  it('rolls back optimistic update on error', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockRejectedValueOnce(new Error('Update failed'))

    // Pre-populate cache with services
    queryClient.setQueryData(servicesKeys.lists(), mockServicesResponse)

    const { result } = renderHook(() => useUpdateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatName: 'test-service',
      updates: { muted: 1 },
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    // Cache should be rolled back to original value
    const cachedData = queryClient.getQueryData<ApiResponse<Service[]>>(servicesKeys.lists())
    expect(cachedData?.results[0].muted).toBe(0)
  })

  it('invalidates queries after successful mutation', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useUpdateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatName: 'test-service',
      updates: { priority: 'p1' },
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: servicesKeys.lists() })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: servicesKeys.detail('test-service') })
  })

  it('updates date_modified on optimistic update', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    queryClient.setQueryData(servicesKeys.lists(), mockServicesResponse)

    const { result } = renderHook(() => useUpdateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatName: 'test-service',
      updates: { team: 'sre' },
    })

    await waitFor(() => {
      const cachedData = queryClient.getQueryData<ApiResponse<Service[]>>(servicesKeys.lists())
      expect(cachedData?.results[0].date_modified).toBeTruthy()
    })
  })
})

describe('useCreateService', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('calls apiClient.createService with correct parameters', async () => {
    const mockCreateService = vi.mocked(apiClient.createService)
    mockCreateService.mockResolvedValueOnce({ success: true, message: 'Created', results: '' })

    const { result } = renderHook(() => useCreateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeat_name: 'new-service',
      service_name: 'New Service',
      alert_interval: 5,
      team: 'platform',
      priority: 'p3',
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockCreateService).toHaveBeenCalledWith({
      heartbeat_name: 'new-service',
      service_name: 'New Service',
      alert_interval: 5,
      team: 'platform',
      priority: 'p3',
    })
  })

  it('invalidates services list on success', async () => {
    const mockCreateService = vi.mocked(apiClient.createService)
    mockCreateService.mockResolvedValueOnce({ success: true, message: 'Created', results: '' })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useCreateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeat_name: 'new-service',
      service_name: 'New Service',
      alert_interval: 5,
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: servicesKeys.lists() })
  })

  it('does not invalidate on error', async () => {
    const mockCreateService = vi.mocked(apiClient.createService)
    mockCreateService.mockRejectedValueOnce(new Error('Create failed'))

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useCreateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeat_name: 'new-service',
      service_name: 'New Service',
      alert_interval: 5,
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    // Should not have been called (onSuccess didn't run)
    expect(invalidateSpy).not.toHaveBeenCalled()
  })

  it('supports optional fields', async () => {
    const mockCreateService = vi.mocked(apiClient.createService)
    mockCreateService.mockResolvedValueOnce({ success: true, message: 'Created', results: '' })

    const { result } = renderHook(() => useCreateService(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeat_name: 'new-service',
      service_name: 'New Service',
      alert_interval: 5,
      threshold: 3,
      runbook: 'https://runbook.example.com/new-service',
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockCreateService).toHaveBeenCalledWith({
      heartbeat_name: 'new-service',
      service_name: 'New Service',
      alert_interval: 5,
      threshold: 3,
      runbook: 'https://runbook.example.com/new-service',
    })
  })
})

describe('useBulkUpdateServices', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('calls apiClient.updateService for each service', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

    const { result } = renderHook(() => useBulkUpdateServices(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatNames: ['service-1', 'service-2', 'service-3'],
      updates: { muted: 1 },
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockUpdateService).toHaveBeenCalledTimes(3)
    expect(mockUpdateService).toHaveBeenCalledWith('service-1', { muted: 1 })
    expect(mockUpdateService).toHaveBeenCalledWith('service-2', { muted: 1 })
    expect(mockUpdateService).toHaveBeenCalledWith('service-3', { muted: 1 })
  })

  it('returns succeeded and failed arrays', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService
      .mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })
      .mockRejectedValueOnce(new Error('Service not found'))
      .mockResolvedValueOnce({ success: true, message: 'Updated', results: '' })

    const { result } = renderHook(() => useBulkUpdateServices(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatNames: ['service-1', 'service-2', 'service-3'],
      updates: { active: 0 },
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual({
      succeeded: ['service-1', 'service-3'],
      failed: [{ heartbeatName: 'service-2', error: 'Service not found' }],
    })
  })

  it('throws error when all updates fail', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockRejectedValue(new Error('Update failed'))

    const { result } = renderHook(() => useBulkUpdateServices(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatNames: ['service-1', 'service-2'],
      updates: { muted: 1 },
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error?.message).toBe('All 2 updates failed')
  })

  it('performs optimistic update on all services', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ success: true, message: 'Updated', results: '' }), 100))
    )

    // Pre-populate cache with multiple services
    const multipleServices: ApiResponse<Service[]> = {
      success: true,
      message: '',
      results: [
        { ...mockService, service_id: 1, heartbeat_name: 'service-1' },
        { ...mockService, service_id: 2, heartbeat_name: 'service-2' },
        { ...mockService, service_id: 3, heartbeat_name: 'service-3' },
      ],
    }
    queryClient.setQueryData(servicesKeys.lists(), multipleServices)

    const { result } = renderHook(() => useBulkUpdateServices(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatNames: ['service-1', 'service-3'],
      updates: { muted: 1 },
    })

    // Check optimistic update immediately
    await waitFor(() => {
      const cachedData = queryClient.getQueryData<ApiResponse<Service[]>>(servicesKeys.lists())
      expect(cachedData?.results[0].muted).toBe(1) // service-1
      expect(cachedData?.results[1].muted).toBe(0) // service-2 (not updated)
      expect(cachedData?.results[2].muted).toBe(1) // service-3
    })
  })

  it('rolls back optimistic update on error', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockRejectedValue(new Error('All failed'))

    // Pre-populate cache
    queryClient.setQueryData(servicesKeys.lists(), mockServicesResponse)

    const { result } = renderHook(() => useBulkUpdateServices(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatNames: ['test-service'],
      updates: { muted: 1 },
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    // Cache should be rolled back
    const cachedData = queryClient.getQueryData<ApiResponse<Service[]>>(servicesKeys.lists())
    expect(cachedData?.results[0].muted).toBe(0)
  })

  it('invalidates all service queries after mutation', async () => {
    const mockUpdateService = vi.mocked(apiClient.updateService)
    mockUpdateService.mockResolvedValue({ success: true, message: 'Updated', results: '' })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useBulkUpdateServices(), {
      wrapper: createWrapper(queryClient),
    })

    result.current.mutate({
      heartbeatNames: ['service-1', 'service-2'],
      updates: { team: 'sre' },
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: servicesKeys.all })
  })
})
