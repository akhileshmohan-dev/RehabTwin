import { Bell, CalendarDays, ChevronDown, Menu } from "lucide-react";

interface HeaderProps {
  onToggleSidebar: () => void;
}

export function Header({ onToggleSidebar }: HeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border/40 bg-background/50 pb-5 pt-1 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="flex size-10 items-center justify-center rounded-xl border border-border bg-card text-foreground md:hidden btn-interactive shadow-sm hover:bg-muted"
          aria-label="Toggle Sidebar"
        >
          <Menu className="size-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-primary tracking-tight">Therapist Dashboard</h1>
          <p className="text-sm text-muted-foreground">Welcome back, Dr. Sharma</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 sm:gap-4">
        <span className="hidden rounded-lg border border-warning/20 bg-warning-soft px-3 py-1.5 text-xs font-semibold text-warning-foreground sm:inline-block">
          Mock Data — Demo Mode
        </span>
        
        <button className="flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground hover:bg-muted/50 transition-colors shadow-sm btn-interactive">
          <CalendarDays className="size-4 text-muted-foreground" />
          <span className="hidden sm:inline">10 Aug 2026 - 17 Aug 2026</span>
          <span className="sm:hidden">10-17 Aug</span>
          <ChevronDown className="size-4 text-muted-foreground" />
        </button>

        <button className="relative flex size-10 items-center justify-center rounded-xl border border-border bg-card hover:bg-muted/50 transition-colors shadow-sm btn-interactive">
          <Bell className="size-5 text-muted-foreground" />
          <span className="absolute right-2 top-2 flex size-2 rounded-full bg-destructive animate-ping" />
          <span className="absolute right-2 top-2 flex size-2 rounded-full bg-destructive" />
        </button>

        <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-1.5 shadow-sm">
          <span className="flex size-8 items-center justify-center rounded-full bg-primary-soft text-xs font-semibold text-primary">
            DS
          </span>
          <span className="hidden text-sm md:block pr-2">
            <span className="block font-semibold text-foreground leading-tight">Dr. Sharma</span>
            <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <span className="size-1.5 rounded-full bg-success" /> Online
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}
