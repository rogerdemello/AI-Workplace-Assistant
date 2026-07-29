import { useState, useRef, useEffect, type KeyboardEvent } from "react";
import { Bell, Search, Command, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useChat } from "@/contexts/ChatContext";
import { getHrNotifications, markHrNotificationRead, type HrNotificationRow } from "@/lib/services";
import { subscribeToSse } from "@/lib/api/client";

export function Topbar({ title, subtitle, action }: { title?: string; subtitle?: string; action?: React.ReactNode }) {
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const { open, send } = useChat();
  const [searchQuery, setSearchQuery] = useState("");
  const [openNotifications, setOpenNotifications] = useState(false);
  const [notifications, setNotifications] = useState<HrNotificationRow[]>([]);
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const notificationsPanelRef = useRef<HTMLDivElement>(null);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const submitSearchToMark = () => {
    const q = searchQuery.trim();
    if (!q) return;
    open();
    void send(q);
    setSearchQuery("");
  };

  const onSearchKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitSearchToMark();
    }
  };

  const refreshNotifications = async (showSpinner = true) => {
    if (session?.role !== "hr" && session?.role !== "admin") return;
    if (showSpinner) setLoadingNotifications(true);
    const rows = await getHrNotifications(20);
    setNotifications(rows);
    if (showSpinner) setLoadingNotifications(false);
  };

  const toggleNotifications = () => {
    const next = !openNotifications;
    setOpenNotifications(next);
    if (next) {
      void refreshNotifications();
    }
  };

  const handleNotificationRead = async (notificationId: string) => {
    const ok = await markHrNotificationRead(notificationId);
    if (!ok) return;
    setNotifications((prev) => prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n)));
  };

  useEffect(() => {
    if (session?.role !== "hr" && session?.role !== "admin") return;
    void refreshNotifications(false);
    const unsubscribe = subscribeToSse("/api/v1/realtime/hr/stream", {
      onEvent: (eventType) => {
        if (eventType === "hr_snapshot") {
          void refreshNotifications(false);
        }
      },
    });
    const timer = window.setInterval(() => {
      void refreshNotifications(false);
    }, 45000);
    return () => {
      unsubscribe();
      window.clearInterval(timer);
    };
  }, [session?.role]);

  useEffect(() => {
    const onOutsideClick = (event: MouseEvent) => {
      if (!openNotifications) return;
      const target = event.target as Node | null;
      if (notificationsPanelRef.current && target && !notificationsPanelRef.current.contains(target)) {
        setOpenNotifications(false);
      }
    };
    window.addEventListener("mousedown", onOutsideClick);
    return () => window.removeEventListener("mousedown", onOutsideClick);
  }, [openNotifications]);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <header className="sticky top-0 z-20 glass border-b border-border">
      <div className="flex items-center gap-4 px-6 lg:px-10 h-16">
        <div className="min-w-0 flex-1">
          {title && <h1 className="text-base font-medium tracking-tight truncate">{title}</h1>}
          {subtitle && <p className="text-xs text-muted-foreground truncate">{subtitle}</p>}
        </div>
        <div className="hidden md:flex items-center gap-2 px-3 h-9 rounded-lg bg-secondary text-muted-foreground text-sm w-72">
          <Search className="size-4 shrink-0" />
          <input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={onSearchKeyDown}
            className="bg-transparent flex-1 outline-none placeholder:text-muted-foreground/70 min-w-0"
            placeholder="Ask MARK — press Enter"
            aria-label="Ask MARK"
          />
          <kbd className="hidden lg:inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-background border border-border shrink-0">
            <Command className="size-3" />K
          </kbd>
        </div>
        {(session?.role === "hr" || session?.role === "admin") && (
          <div className="relative" ref={notificationsPanelRef}>
            <Button variant="ghost" size="icon" className="rounded-full" type="button" title="Notifications" aria-label="Notifications" onClick={toggleNotifications}>
              <Bell className="size-4" />
              {unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-danger" />
              )}
            </Button>
            {openNotifications && (
              <div className="absolute right-0 mt-2 w-80 rounded-xl border border-border bg-card shadow-elevated p-3 z-50">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Notifications</div>
                  <button type="button" className="text-xs underline" onClick={() => void refreshNotifications()}>Refresh</button>
                </div>
                {loadingNotifications ? (
                  <div className="text-sm text-muted-foreground py-3">Loading notifications...</div>
                ) : notifications.length === 0 ? (
                  <div className="text-sm text-muted-foreground py-3">No notifications yet.</div>
                ) : (
                  <ul className="space-y-2 max-h-80 overflow-auto">
                    {notifications.map((n) => (
                      <li key={n.id} className="rounded-lg border border-border p-2.5">
                        <div className="flex items-start justify-between gap-2">
                          <div className="text-sm font-medium">{n.title}</div>
                          {!n.is_read && (
                            <button type="button" className="text-[11px] underline" onClick={() => void handleNotificationRead(n.id)}>
                              Mark read
                            </button>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">{n.body || "No additional details."}</div>
                        <div className="text-[11px] mt-1.5 text-muted-foreground capitalize">{n.notification_type.replaceAll("_", " ")}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
        {session ? (
          <Button variant="outline" size="sm" onClick={handleLogout} className="gap-2">
            <LogOut className="size-4" />
            Logout
          </Button>
        ) : null}
        {action}
      </div>
    </header>
  );
}
