/**
 * Table Pagination Component
 *
 * A reusable pagination component that manages page state via URL query params.
 * Uses shadcn/ui Pagination primitives with Linq brand styling.
 */

import { useSearchParams } from 'react-router-dom'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { cn } from '@/lib/utils'

/**
 * Props for the TablePagination component
 */
export interface TablePaginationProps {
  /** Total number of items across all pages */
  totalItems: number
  /** Number of items per page (default: 25) */
  pageSize?: number
  /** URL query param name for current page (default: 'page') */
  pageParam?: string
  /** Maximum number of page buttons to show (default: 5) */
  maxPageButtons?: number
  /** Additional className for the pagination container */
  className?: string
}

/**
 * Calculate the range of page numbers to display
 */
function getPageRange(
  currentPage: number,
  totalPages: number,
  maxButtons: number
): number[] {
  if (totalPages <= maxButtons) {
    return Array.from({ length: totalPages }, (_, i) => i + 1)
  }

  const halfButtons = Math.floor(maxButtons / 2)
  let start = currentPage - halfButtons
  let end = currentPage + halfButtons

  if (start < 1) {
    start = 1
    end = maxButtons
  }

  if (end > totalPages) {
    end = totalPages
    start = totalPages - maxButtons + 1
  }

  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
}

/**
 * Hook to manage pagination state via URL search params
 */
export function usePagination(pageParam = 'page', pageSize = 25) {
  const [searchParams, setSearchParams] = useSearchParams()

  const currentPage = Math.max(1, parseInt(searchParams.get(pageParam) || '1', 10))

  const setPage = (page: number) => {
    const newParams = new URLSearchParams(searchParams)
    if (page === 1) {
      newParams.delete(pageParam)
    } else {
      newParams.set(pageParam, String(page))
    }
    setSearchParams(newParams)
  }

  return {
    currentPage,
    setPage,
    pageSize,
    offset: (currentPage - 1) * pageSize,
  }
}

/**
 * Table Pagination Component
 *
 * Displays pagination controls (Previous, page numbers, Next) with URL state management.
 * Styled with Linq brand colors.
 *
 * @example
 * ```tsx
 * const services = data?.results ?? []
 * const { currentPage, pageSize, offset } = usePagination()
 * const paginatedServices = services.slice(offset, offset + pageSize)
 *
 * return (
 *   <>
 *     <Table>...</Table>
 *     <TablePagination totalItems={services.length} />
 *   </>
 * )
 * ```
 */
export function TablePagination({
  totalItems,
  pageSize = 25,
  pageParam = 'page',
  maxPageButtons = 5,
  className,
}: TablePaginationProps) {
  const { currentPage, setPage } = usePagination(pageParam, pageSize)

  const totalPages = Math.ceil(totalItems / pageSize)

  // Don't show pagination if there's only one page or no items
  if (totalPages <= 1) {
    return null
  }

  const pageRange = getPageRange(currentPage, totalPages, maxPageButtons)
  const showStartEllipsis = pageRange[0] > 1
  const showEndEllipsis = pageRange[pageRange.length - 1] < totalPages

  const handlePrevious = () => {
    if (currentPage > 1) {
      setPage(currentPage - 1)
    }
  }

  const handleNext = () => {
    if (currentPage < totalPages) {
      setPage(currentPage + 1)
    }
  }

  const handlePageClick = (page: number) => {
    setPage(page)
  }

  return (
    <Pagination className={cn('mt-4', className)}>
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            onClick={handlePrevious}
            className={cn(
              'cursor-pointer select-none',
              currentPage === 1 && 'pointer-events-none opacity-50'
            )}
            aria-disabled={currentPage === 1}
          />
        </PaginationItem>

        {showStartEllipsis && (
          <>
            <PaginationItem>
              <PaginationLink
                onClick={() => handlePageClick(1)}
                className="cursor-pointer select-none"
              >
                1
              </PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationEllipsis />
            </PaginationItem>
          </>
        )}

        {pageRange.map((page) => (
          <PaginationItem key={page}>
            <PaginationLink
              isActive={page === currentPage}
              onClick={() => handlePageClick(page)}
              className={cn(
                'cursor-pointer select-none',
                page === currentPage &&
                  'bg-linq-blue text-white border-linq-blue hover:bg-linq-blue/90 hover:text-white'
              )}
            >
              {page}
            </PaginationLink>
          </PaginationItem>
        ))}

        {showEndEllipsis && (
          <>
            <PaginationItem>
              <PaginationEllipsis />
            </PaginationItem>
            <PaginationItem>
              <PaginationLink
                onClick={() => handlePageClick(totalPages)}
                className="cursor-pointer select-none"
              >
                {totalPages}
              </PaginationLink>
            </PaginationItem>
          </>
        )}

        <PaginationItem>
          <PaginationNext
            onClick={handleNext}
            className={cn(
              'cursor-pointer select-none',
              currentPage === totalPages && 'pointer-events-none opacity-50'
            )}
            aria-disabled={currentPage === totalPages}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  )
}
