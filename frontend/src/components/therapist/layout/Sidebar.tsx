import {
  Activity,
  BarChart3,
  Bell,
  CalendarDays,
  ChevronDown,
  Dumbbell,
  FileText,
  LayoutDashboard,
  LogOut,
  Settings,
  Users,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { DATA_SOURCE } from "@/data/rehabService";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Patients", icon: Users },
  { label: "Sessions", icon: CalendarDays },
  { label: "Exercises", icon: Dumbbell },
  { label: "Alerts", icon: Bell, badge: 3 },
  { label: "Reports", icon: FileText },
  { label: "Analytics", icon: BarChart3 },
  { label: "Settings", icon: Settings },
];

interface SidebarProps {
  active: string;
  onSelect: (label: string) => void;
  onClose?: () => void;
}

export function Sidebar({ active, onSelect, onClose }: SidebarProps) {
  const handleSelect = (label: string) => {
    onSelect(label);
    if (onClose) onClose();
  };

  return (
    <aside className="relative flex h-screen w-[260px] shrink-0 flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border shadow-2xl">
      {onClose ? (
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-5 flex size-8 items-center justify-center rounded-lg hover:bg-sidebar-accent text-sidebar-foreground/60 hover:text-sidebar-accent-foreground md:hidden btn-interactive"
          aria-label="Close menu"
        >
          <X className="size-4" />
        </button>
      ) : null}

      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex size-10 items-center justify-center rounded-xl bg-sidebar-accent border border-sidebar-border/30">
          <Activity className="size-5 text-primary" strokeWidth={2.5} />
        </div>
        <div>
          <p className="text-lg font-bold text-sidebar-accent-foreground tracking-tight">RehabTwin</p>
          <p className="text-xs text-sidebar-foreground/50">Therapist Dashboard</p>
        </div>
      </div>

      <nav className="flex flex-col gap-1 px-4 mt-2">
        {navItems.map((item) => {
          const isActive = item.label === active;
          return (
            <button
              key={item.label}
              type="button"
              onClick={() => handleSelect(item.label)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all btn-interactive duration-200",
                isActive
                  ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-lg shadow-primary/10"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              )}
            >
              <item.icon className={cn("size-[18px] transition-transform duration-300", isActive && "scale-110")} />
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge ? (
                <span className="flex size-5 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground">
                  {item.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </nav>

      <div className="mt-auto space-y-4 p-4">
        <div className="rounded-xl bg-sidebar-accent/50 p-4 border border-sidebar-border/30">
          <p className="text-[10px] uppercase font-bold tracking-wider text-sidebar-foreground/45">Data Source</p>
          <p className="mt-1.5 flex items-center gap-2 text-xs font-semibold text-sidebar-accent-foreground">
            <span className="size-1.5 rounded-full bg-success animate-pulse" />
            {DATA_SOURCE}
          </p>
          <p className="text-[10px] text-sidebar-foreground/40">(Demo Mode)</p>
        </div>

        <div className="flex items-center gap-3 rounded-xl px-2 py-2 bg-sidebar-accent/20 border border-sidebar-border/10">
          <div className="flex size-9 items-center justify-center rounded-full bg-sidebar-accent text-sm font-semibold text-sidebar-accent-foreground font-sans">
            DS
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-sidebar-accent-foreground truncate">Dr. Sharma</p>
            <p className="text-xs text-sidebar-foreground/50 truncate">Physiotherapist</p>
          </div>
          <ChevronDown className="size-4 text-sidebar-foreground/40" />
        </div>

        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground btn-interactive transition-colors"
        >
          <LogOut className="size-[18px] rotate-180" />
          Logout
        </button>
      </div>
    </aside>
  );
}
