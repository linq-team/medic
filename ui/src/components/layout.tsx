import { useState } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Server,
  AlertTriangle,
  BookOpen,
  ScrollText,
  Settings,
} from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/services', label: 'Services', icon: Server },
  { to: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { to: '/playbooks', label: 'Playbooks', icon: BookOpen },
  { to: '/audit-logs', label: 'Audit Logs', icon: ScrollText },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function NavLink({
  item,
  onClick,
}: {
  item: NavItem
  onClick?: () => void
}) {
  const location = useLocation()
  const isActive = location.pathname === item.to
  const Icon = item.icon

  return (
    <Link
      to={item.to}
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
      )}
    >
      <Icon className="h-5 w-5 flex-shrink-0" />
      <span>{item.label}</span>
    </Link>
  )
}

function DesktopSidebar() {
  return (
    <aside className="hidden md:flex w-64 border-r border-border bg-card flex-col">
      <nav className="flex flex-col gap-1 p-4">
        {navItems.map((item) => (
          <NavLink key={item.to} item={item} />
        ))}
      </nav>
    </aside>
  )
}

function MobileSidebar({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-64 p-0">
        <SheetHeader className="px-6 py-4 border-b border-border">
          <SheetTitle className="flex items-center gap-3">
            <img
              src="/assets/medic-icon-all-green.png"
              alt="Medic Logo"
              className="h-8 w-8"
            />
            <span>Medic UI</span>
          </SheetTitle>
        </SheetHeader>
        <nav className="flex flex-col gap-1 p-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              item={item}
              onClick={() => onOpenChange(false)}
            />
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  )
}

function Header({ onMenuClick }: { onMenuClick: () => void }) {
  return (
    <header className="border-b border-border bg-card">
      <div className="px-4 md:px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Mobile hamburger menu button */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={onMenuClick}
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <img
            src="/assets/medic-icon-all-green.png"
            alt="Medic Logo"
            className="h-8 w-8"
          />
          <h1 className="text-xl font-bold text-foreground">Medic UI</h1>
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}

export function Layout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  return (
    <div className="min-h-screen bg-background font-sans flex">
      {/* Desktop sidebar */}
      <DesktopSidebar />

      {/* Mobile sidebar (sheet) */}
      <MobileSidebar open={mobileNavOpen} onOpenChange={setMobileNavOpen} />

      {/* Main content area */}
      <div className="flex-1 flex flex-col">
        {/* Header with hamburger menu for mobile */}
        <Header onMenuClick={() => setMobileNavOpen(true)} />

        {/* Page content rendered via Outlet */}
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
