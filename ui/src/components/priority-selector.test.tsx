/**
 * Tests for Priority Selector Component
 *
 * Note: Radix UI Select uses portals which have known testing limitations.
 * These tests focus on the component's initial render state and basic behavior.
 * The Select dropdown interaction is tested via E2E tests instead.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { PrioritySelector } from './priority-selector'
import type { Service } from '@/lib/api'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      updateService: vi.fn(),
    },
  }
})

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

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
const mockServiceP3: Service = {
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

const mockServiceP1: Service = {
  ...mockServiceP3,
  priority: 'p1',
}

const mockServiceP2: Service = {
  ...mockServiceP3,
  priority: 'P2', // Uppercase to test normalization
}

describe('PrioritySelector', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('renders select with current priority value', () => {
    render(<PrioritySelector service={mockServiceP3} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).toBeInTheDocument()
    expect(selectTrigger).toHaveAttribute('aria-label', 'Change priority for Test Service')
    expect(selectTrigger).toHaveTextContent('P3')
  })

  it('renders P1 priority with error styling', () => {
    render(<PrioritySelector service={mockServiceP1} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).toHaveTextContent('P1')
    expect(selectTrigger).toHaveClass('text-status-error')
  })

  it('renders P2 priority with warning styling (case insensitive)', () => {
    render(<PrioritySelector service={mockServiceP2} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).toHaveTextContent('P2')
    expect(selectTrigger).toHaveClass('text-status-warning')
  })

  it('renders P3 priority with muted styling', () => {
    render(<PrioritySelector service={mockServiceP3} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).toHaveClass('text-muted-foreground')
  })

  it('handles service with empty priority (defaults to P3)', () => {
    const serviceNoPriority: Service = {
      ...mockServiceP3,
      priority: '',
    }

    render(<PrioritySelector service={serviceNoPriority} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).toHaveTextContent('P3')
  })

  it('has correct compact styling for inline use', () => {
    render(<PrioritySelector service={mockServiceP3} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    // Compact styling: small height, narrow width, no visible border
    expect(selectTrigger).toHaveClass('h-7', 'w-16', 'border-none', 'bg-transparent')
  })

  it('is not disabled by default', () => {
    render(<PrioritySelector service={mockServiceP3} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).not.toBeDisabled()
  })

  it('displays correct accessibility label', () => {
    render(<PrioritySelector service={mockServiceP1} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).toHaveAttribute('aria-label', 'Change priority for Test Service')
  })

  it('shows P1 value in trigger for high priority service', () => {
    render(<PrioritySelector service={mockServiceP1} />, {
      wrapper: createWrapper(queryClient),
    })

    expect(screen.getByText('P1')).toBeInTheDocument()
  })

  it('normalizes uppercase priority values', () => {
    // P2 is uppercase in mockServiceP2
    render(<PrioritySelector service={mockServiceP2} />, {
      wrapper: createWrapper(queryClient),
    })

    const selectTrigger = screen.getByRole('combobox')
    expect(selectTrigger).toHaveTextContent('P2')
  })
})
