import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useChat } from "@/contexts/ChatContext";
import { AppLayout } from "@/components/layout/AppLayout";
import { Sparkles } from "lucide-react";

export default function ChatPage() {
  const { expand } = useChat();
  const nav = useNavigate();

  useEffect(() => {
    expand();
  }, [expand]);

  return (
    <AppLayout title="Conversations" subtitle="Your full chat with MARK">
      <div className="px-6 lg:px-10 py-16 max-w-2xl mx-auto text-center">
        <div className="size-16 mx-auto rounded-2xl bg-teal-grad grid place-items-center shadow-glow mb-6">
          <Sparkles className="size-7 text-primary-foreground" />
        </div>
        <h2 className="font-display text-3xl tracking-tight">Chat is open in full screen.</h2>
        <p className="mt-3 text-muted-foreground">Close it anytime to return here. Your conversation is always saved.</p>
        <button onClick={() => nav("/employee")} className="mt-8 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary hover:bg-secondary/70 text-sm transition-colors">
          Back to My Day
        </button>
      </div>
    </AppLayout>
  );
}
