import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import type { ReactNode } from "react";

interface AppLayoutProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  topbarAction?: ReactNode;
}

export function AppLayout({ children, title, subtitle, topbarAction }: AppLayoutProps) {
  return (
    <div className="flex h-full min-h-screen w-full bg-background">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={title} subtitle={subtitle} action={topbarAction} />
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {children}
        </main>
      </div>
    </div>
  );
}
