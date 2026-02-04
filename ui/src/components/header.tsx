import { ThemeToggle } from '@/components/theme-toggle'

export function Header() {
  return (
    <header className="border-b border-border bg-card">
      <div className="px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
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
