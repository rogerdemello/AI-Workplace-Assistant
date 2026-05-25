import { Fragment } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import type { ChatRecord } from "@/types/chat";
import { cn } from "@/lib/utils";

interface Props {
  message: ChatRecord;
}

// Matches in-app paths (/surveys?survey=…) and absolute http(s) URLs. React
// escapes the non-matched text, so this is safe against injection.
const LINK_RE = /(https?:\/\/[^\s]+|\/[A-Za-z0-9/_\-?=&%.]+)/g;

function renderWithLinks(text: string) {
  const parts = text.split(LINK_RE);
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      if (/^https?:\/\//.test(part)) {
        return (
          <a key={i} href={part} target="_blank" rel="noreferrer" className="underline hover:opacity-80">
            {part}
          </a>
        );
      }
      return (
        <Link key={i} to={part} className="underline hover:opacity-80">
          {part}
        </Link>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
      className={cn("flex gap-3 mb-4", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="size-8 shrink-0 rounded-full bg-ink grid place-items-center text-primary-foreground border border-border">
          <Sparkles className="size-3.5 text-accent-glow" />
        </div>
      )}
      <div className={cn("max-w-[78%] space-y-2", isUser && "items-end flex flex-col")}>
        <div className={cn(
          "px-4 py-2.5 rounded-2xl text-sm leading-relaxed",
          isUser
            ? "bg-ink text-primary-foreground rounded-br-md"
            : "bg-secondary text-foreground rounded-bl-md"
        )}>
          <span className="whitespace-pre-wrap">{renderWithLinks(message.text)}</span>
        </div>

        {/* Keep message bubble minimal; structured controls render in ChatPanel. */}
      </div>
      {isUser && (
        <div className="size-8 shrink-0 rounded-full bg-teal-grad grid place-items-center text-primary-foreground text-[11px] font-medium">AM</div>
      )}
    </motion.div>
  );
}
