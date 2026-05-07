import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Home, Ticket, Users, BarChart3, Mail, Shield, MessageSquare, Sparkles, UserCircle2, Briefcase, LogOut, CreditCard, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth, type UserRole } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";

type NavItem = { to: string; icon: typeof Home; label: string; roles?: UserRole[] };

const sections: { label: string; items: NavItem[] }[] = [
  {
    label: "You",
    items: [
      { to: "/employee", icon: Home, label: "My Day", roles: ["employee"] },
      { to: "/chat", icon: MessageSquare, label: "Conversations" },
    ],
  },
  {
    label: "People Ops",
    items: [
      { to: "/dashboard", icon: BarChart3, label: "Pulse", roles: ["hr"] },
      { to: "/tickets", icon: Ticket, label: "Tickets" },
      { to: "/employees", icon: Users, label: "Employees", roles: ["hr"] },
      { to: "/manager", icon: Briefcase, label: "Manager" },
      { to: "/surveys", icon: Sparkles, label: "Surveys" },
    ],
  },
  {
    label: "Tools",
    items: [
      { to: "/email-assistant", icon: Mail, label: "Email Assistant", roles: ["hr"] },
      { to: "/knowledge-base", icon: BookOpen, label: "Knowledge Base", roles: ["hr"] },
      { to: "/billing", icon: CreditCard, label: "Billing", roles: ["hr"] },
      { to: "/admin", icon: Shield, label: "Admin", roles: ["hr"] },
    ],
  },
];

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { session, logout } = useAuth();

  const userInitials = session?.name
    ?.split(" ")
    .map((namePart) => namePart[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "MK";

  const userRoleLabel = session?.role === "hr" ? "HR" : "Employee";

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const visibleSections = sections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        if (!item.roles?.length) return true;
        return session?.role && item.roles.includes(session.role);
      }),
    }))
    .filter((section) => section.items.length > 0);

  return (
    <aside className="hidden md:flex w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border">
      <div className="px-6 py-6 flex items-center gap-2">
        <div className="size-8 rounded-xl bg-teal-grad grid place-items-center shadow-glow">
          <span className="font-display text-primary-foreground text-lg leading-none">M</span>
        </div>
        <div>
          <div className="text-sidebar-accent-foreground font-semibold tracking-tight">MARK</div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/60">HR · Operating System</div>
        </div>
      </div>

      <nav className="flex-1 px-3 space-y-6 overflow-y-auto scrollbar-thin">
        {visibleSections.map((section) => (
          <div key={section.label}>
            <div className="px-3 mb-2 text-[10px] uppercase tracking-[0.18em] text-sidebar-foreground/40">{section.label}</div>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = location.pathname === item.to || (item.to !== "/" && location.pathname.startsWith(item.to));
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all",
                        active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent/40 hover:text-sidebar-accent-foreground",
                      )}
                    >
                      {active && (
                        <motion.span layoutId="sidebar-indicator" className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent" />
                      )}
                      <item.icon className="size-4 shrink-0" />
                      <span>{item.label}</span>
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="p-3 m-3 rounded-xl bg-sidebar-accent/40 border border-sidebar-border/60 flex items-center gap-3">
        <div className="size-9 rounded-full bg-teal-grad grid place-items-center text-primary-foreground text-xs font-medium">{userInitials}</div>
        <div className="min-w-0">
          <div className="text-sm text-sidebar-accent-foreground truncate">{session?.name || "MARK User"}</div>
          <div className="text-[11px] text-sidebar-foreground/60 truncate">{userRoleLabel}</div>
        </div>
        <UserCircle2 className="size-4 text-sidebar-foreground/40" />
      </div>
      <div className="px-3 pb-4">
        <Button variant="secondary" className="w-full justify-start gap-2" onClick={handleLogout}>
          <LogOut className="size-4" />
          Logout
        </Button>
      </div>
    </aside>
  );
}
