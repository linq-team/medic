/**
 * Tests for History page - Service change history with filters and restore functionality
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { type ReactNode } from 'react'
import { History } from './History'
import { apiClient, type Snapshot } from '@/lib/api'
import { toast } from 'sonner'

// Mock the apiClient
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    apiClient: {
      getSnapshots: vi.fn(),
      restoreSnapshot: vi.fn(),
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

// Mock snapshot data
const mockSnapshot: Snapshot = {
  snapshot_id: 1,
  service_id: 1,
  snapshot_data: {
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
    runbook: 'https://example.com/runbook',
    date_added: '2026-01-01T00:00:00Z',
    date_modified: null,
    date_muted: null,
  },
  action_type: 'edit',
  actor: 'user@example.com',
  created_at: '2026-02-01T12:00:00Z',
  restored_at: null,
}

const mockRestoredSnapshot: Snapshot = {
  ...mockSnapshot,
  snapshot_id: 2,
  action_type: 'mute',
  created_at: '2026-01-15T12:00:00Z',
  restored_at: '2026-01-20T14:30:00Z',
}

// Wrapper component with providers
function createWrapper(queryClient: QueryClient, initialEntry = '/history') {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/history" element={children} />
            <Route path="/services/:id" element={<div>Service Detail</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }
}

// Helper to render the page
function renderPage(queryClient?: QueryClient, initialEntry?: string) {
  const qc = queryClient ?? createTestQueryClient()
  const Wrapper = createWrapper(qc, initialEntry)
  return {
    ...render(
      <Wrapper>
        <History />
      </Wrapper>
    ),
    queryClient: qc,
  }
}

describe('History Page', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = createTestQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    queryClient.clear()
  })

  describe('rendering', () => {
    it('renders page title and description', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Service History/i })).toBeInTheDocument()
        expect(
          screen.getByText(/View and restore service changes across all services/)
        ).toBeInTheDocument()
      })
    })

    it('renders filter controls', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Search services/i)).toBeInTheDocument()
        expect(screen.getByText('Action Type')).toBeInTheDocument()
        expect(screen.getByText('Start Date')).toBeInTheDocument()
        expect(screen.getByText('End Date')).toBeInTheDocument()
      })
    })

    it('shows loading skeleton while fetching', () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      // Never resolve to keep loading state
      mockGetSnapshots.mockReturnValue(new Promise(() => {}))

      renderPage(queryClient)

      // Loading skeleton should be present
      expect(screen.getByRole('heading', { name: /Service History/i })).toBeInTheDocument()
    })

    it('shows empty state when no snapshots exist', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('No history found')).toBeInTheDocument()
        expect(
          screen.getByText(/Service change history will appear here/)
        ).toBeInTheDocument()
      })
    })

    it('shows error state when API fails', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockRejectedValueOnce(new Error('Network error'))

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Error loading history')).toBeInTheDocument()
      })
    })
  })

  describe('snapshot list', () => {
    it('renders snapshot table with correct columns', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        // Check for table headers
        expect(screen.getByRole('columnheader', { name: /Service/i })).toBeInTheDocument()
        expect(screen.getByRole('columnheader', { name: /Action/i })).toBeInTheDocument()
        expect(screen.getByRole('columnheader', { name: /Actor/i })).toBeInTheDocument()
        expect(screen.getByRole('columnheader', { name: /Date/i })).toBeInTheDocument()
        expect(screen.getByRole('columnheader', { name: /Status/i })).toBeInTheDocument()
      })
    })

    it('renders snapshot data correctly', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        // Service name
        expect(screen.getByText('Test Service')).toBeInTheDocument()
        // Heartbeat name
        expect(screen.getByText('test-service')).toBeInTheDocument()
        // Action type badge
        expect(screen.getByText('Edited')).toBeInTheDocument()
        // Actor
        expect(screen.getByText('user@example.com')).toBeInTheDocument()
        // Restore button
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })
    })

    it('shows Restored badge for already-restored snapshots', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [mockRestoredSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Restored')).toBeInTheDocument()
        // Should not show Restore button for already-restored snapshot
        expect(screen.queryByRole('button', { name: /Restore/i })).not.toBeInTheDocument()
      })
    })

    it('links service name to service detail page', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        const serviceLink = screen.getByRole('link', { name: /Test Service/i })
        expect(serviceLink).toHaveAttribute('href', '/services/test-service')
      })
    })
  })

  describe('action type display', () => {
    it('displays correct badge for edit action', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Edited')).toBeInTheDocument()
      })
    })

    it('displays correct badge for mute action', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [{ ...mockSnapshot, action_type: 'mute' }],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Muted')).toBeInTheDocument()
      })
    })

    it('displays correct badge for deactivate action', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [{ ...mockSnapshot, action_type: 'deactivate' }],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Deactivated')).toBeInTheDocument()
      })
    })

    it('displays correct badge for priority_change action', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [{ ...mockSnapshot, action_type: 'priority_change' }],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Priority Changed')).toBeInTheDocument()
      })
    })
  })

  describe('filters', () => {
    it('loads snapshots with filter params from URL', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, '/history?action_type=mute')

      await waitFor(() => {
        // Should have called getSnapshots with the action_type filter from URL
        expect(mockGetSnapshots).toHaveBeenCalledWith(
          expect.objectContaining({
            action_type: 'mute',
          })
        )
      })
    })

    it('shows Clear filters button when filters are active', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, '/history?action_type=mute')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Clear filters/i })).toBeInTheDocument()
      })
    })

    it('shows no matching history message when filters return empty', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [],
          total_count: 0,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient, '/history?action_type=mute')

      await waitFor(() => {
        expect(screen.getByText('No matching history')).toBeInTheDocument()
        expect(
          screen.getByText(/No snapshots match your current filters/)
        ).toBeInTheDocument()
      })
    })
  })

  describe('restore functionality', () => {
    it('opens restore confirmation dialog when Restore button is clicked', async () => {
      const user = userEvent.setup()
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
        expect(screen.getByText('Restore Service')).toBeInTheDocument()
        expect(screen.getByText(/Are you sure you want to restore/)).toBeInTheDocument()
      })
    })

    it('shows snapshot state preview in restore dialog', async () => {
      const user = userEvent.setup()
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByText('This will restore the following state:')).toBeInTheDocument()
        expect(screen.getByText('Service Name:')).toBeInTheDocument()
        expect(screen.getByText('Active:')).toBeInTheDocument()
        expect(screen.getByText('Muted:')).toBeInTheDocument()
        expect(screen.getByText('Priority:')).toBeInTheDocument()
      })
    })

    it('closes dialog when Cancel is clicked', async () => {
      const user = userEvent.setup()
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Close dialog
      const dialog = screen.getByRole('dialog')
      const cancelButton = within(dialog).getByRole('button', { name: /Cancel/i })
      await user.click(cancelButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })

    it('calls restoreSnapshot when Restore is confirmed', async () => {
      const user = userEvent.setup()
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)

      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockResolvedValueOnce({
        success: true,
        message: 'Restored',
        results: { ...mockSnapshot, restored_at: '2026-02-05T12:00:00Z' },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockRestoreSnapshot).toHaveBeenCalledWith(1, undefined)
      })
    })

    it('shows success toast when restore succeeds', async () => {
      const user = userEvent.setup()
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
      const mockToastSuccess = vi.mocked(toast.success)

      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockResolvedValueOnce({
        success: true,
        message: 'Restored',
        results: { ...mockSnapshot, restored_at: '2026-02-05T12:00:00Z' },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith(expect.stringContaining('restored'))
      })
    })

    it('shows error toast when restore fails', async () => {
      const user = userEvent.setup()
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)
      const mockToastError = vi.mocked(toast.error)

      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockRejectedValueOnce(new Error('Restore failed'))

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith(expect.stringContaining('Failed'))
      })
    })

    it('closes dialog after restore succeeds', async () => {
      const user = userEvent.setup()
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      const mockRestoreSnapshot = vi.mocked(apiClient.restoreSnapshot)

      mockGetSnapshots.mockResolvedValue({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })
      mockRestoreSnapshot.mockResolvedValueOnce({
        success: true,
        message: 'Restored',
        results: { ...mockSnapshot, restored_at: '2026-02-05T12:00:00Z' },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Restore/i })).toBeInTheDocument()
      })

      // Open dialog
      const restoreButton = screen.getByRole('button', { name: /Restore/i })
      await user.click(restoreButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      // Confirm restore
      const dialog = screen.getByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: /^Restore$/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })
  })

  describe('pagination', () => {
    it('shows pagination when there are multiple pages', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: Array(25).fill(mockSnapshot).map((s, i) => ({
            ...s,
            snapshot_id: i + 1,
          })),
          total_count: 50,
          limit: 25,
          offset: 0,
          has_more: true,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        // Should show pagination navigation
        expect(screen.getByText('Next')).toBeInTheDocument()
        expect(screen.getByText('1')).toBeInTheDocument()
        expect(screen.getByText('2')).toBeInTheDocument()
      })
    })

    it('does not show pagination when there is only one page', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: [mockSnapshot],
          total_count: 1,
          limit: 25,
          offset: 0,
          has_more: false,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText('Test Service')).toBeInTheDocument()
      })

      // Should not show pagination navigation
      expect(screen.queryByText('Next')).not.toBeInTheDocument()
      expect(screen.queryByText('Previous')).not.toBeInTheDocument()
    })

    it('shows results summary with correct counts', async () => {
      const mockGetSnapshots = vi.mocked(apiClient.getSnapshots)
      mockGetSnapshots.mockResolvedValueOnce({
        success: true,
        message: 'OK',
        results: {
          entries: Array(25).fill(mockSnapshot).map((s, i) => ({
            ...s,
            snapshot_id: i + 1,
          })),
          total_count: 50,
          limit: 25,
          offset: 0,
          has_more: true,
        },
      })

      renderPage(queryClient)

      await waitFor(() => {
        expect(screen.getByText(/Showing 1 to 25 of 50 entries/)).toBeInTheDocument()
      })
    })
  })
})
