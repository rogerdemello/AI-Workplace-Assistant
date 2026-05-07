import { motion, AnimatePresence } from "framer-motion";
import { useChat } from "@/contexts/ChatContext";
import { Sparkles, MessageSquare } from "lucide-react";

export function ChatLauncher() {
  const { mode, open, unreadCount } = useChat();
  if (mode !== "minimized") return null;

  return (
    <AnimatePresence>
      <motion.button
        key="launcher"
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0, opacity: 0 }}
        transition={{ type: "spring", stiffness: 400, damping: 28 }}
        onClick={open}
        className="fixed bottom-6 right-6 z-50 group"
        aria-label="Open MARK chat"
      >
        <span className="absolute inset-0 rounded-full animate-glow-pulse" />
        <span className="relative flex items-center gap-3 pl-3 pr-5 h-14 rounded-full bg-ink text-primary-foreground shadow-elevated border border-white/10 hover:scale-[1.02] transition-transform">
          <span className="size-9 rounded-full bg-teal-grad grid place-items-center">
            <Sparkles className="size-4" />
          </span>
          <span className="flex flex-col items-start leading-tight">
            <span className="text-sm font-medium">Ask MARK</span>
            <span className="text-[10px] text-primary-foreground/60">Always here</span>
          </span>
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 size-5 rounded-full bg-accent text-accent-foreground text-[10px] grid place-items-center font-medium">
              {unreadCount}
            </span>
          )}
        </span>
      </motion.button>
    </AnimatePresence>
  );
}
