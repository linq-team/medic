import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Server,
  AlertTriangle,
  BookOpen,
  ScrollText,
  History,
  Settings,
} from 'lucide-react'
import { cn } from '@/lib/utils'

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
  { to: '/history', label: 'History', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function NavLink({ item }: { item: NavItem }) {
  const location = useLocation()
  const isActive = location.pathname === item.to
  const Icon = item.icon

  return (
    <Link
      to={item.to}
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

export function Sidebar() {
  return (
    <aside className="w-64 border-r border-border bg-card">
      <nav className="flex flex-col gap-1 p-4">
        {navItems.map((item) => (
          <NavLink key={item.to} item={item} />
        ))}
      </nav>
    </aside>
  )
}
