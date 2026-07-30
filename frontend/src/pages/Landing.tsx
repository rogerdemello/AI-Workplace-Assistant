import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, MessageSquare, ShieldCheck, Zap, HeartHandshake } from "lucide-react";
import { useChat } from "@/contexts/ChatContext";

export default function Landing() {
  const { open } = useChat();

  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">
      {/* Nav */}
      <nav className="absolute top-0 inset-x-0 z-30 px-6 lg:px-12 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="size-8 rounded-xl bg-teal-grad grid place-items-center shadow-glow">
            <span className="font-display text-primary-foreground text-lg leading-none">M</span>
          </div>
          <span className="font-medium tracking-tight">MARK</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-muted-foreground">
          <a href="#why" className="hover:text-foreground transition-colors">Why MARK</a>
          <a href="#how" className="hover:text-foreground transition-colors">How it works</a>
          <Link to="/dashboard" className="hover:text-foreground transition-colors">For HR</Link>
        </div>
        <Link to="/login" className="text-sm px-4 py-2 rounded-lg bg-secondary hover:bg-secondary/70 transition-colors">
          Sign in
        </Link>
      </nav>

      {/* Hero */}
      <section className="relative pt-40 pb-32 px-6 lg:px-12">
        <div className="absolute inset-0 bg-aurora pointer-events-none" />
        <div className="absolute -top-40 -right-40 size-[700px] rounded-full bg-accent/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-40 -left-40 size-[700px] rounded-full bg-emerald/10 blur-3xl pointer-events-none" />

        <div className="relative max-w-5xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-card border border-border text-xs text-muted-foreground mb-8 shadow-soft"
          >
            <span className="size-1.5 rounded-full bg-emerald animate-pulse-soft" />
            Now in private beta with 40+ teams
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-[clamp(2.5rem,8vw,5.5rem)] leading-[0.95] tracking-tight text-balance"
          >
            HR that listens<br />
            <span className="italic text-muted-foreground">before</span> it answers.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="mt-8 text-lg text-muted-foreground max-w-xl mx-auto text-balance"
          >
            MARK is the conversational AI that runs your people operations. Employees just talk — leave, policies, complaints, support — it all happens in one place.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25 }}
            className="mt-10 flex flex-wrap items-center justify-center gap-3"
          >
            <button onClick={open} className="group inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-ink text-primary-foreground text-sm font-medium shadow-elevated hover:scale-[1.02] transition-transform">
              <MessageSquare className="size-4" />
              Try MARK now
              <ArrowRight className="size-4 group-hover:translate-x-0.5 transition-transform" />
            </button>
            <Link to="/dashboard" className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-card border border-border text-sm hover:border-foreground/30 transition-colors">
              See HR view
            </Link>
          </motion.div>

          {/* Hero chat preview */}
          <motion.div
            initial={{ opacity: 0, y: 40, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.9, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="mt-20 max-w-2xl mx-auto"
          >
            <div className="rounded-2xl bg-card border border-border shadow-chat overflow-hidden text-left">
              <div className="px-5 py-3 bg-ink text-primary-foreground border-b border-white/5 flex items-center gap-3 relative">
                <div className="absolute inset-0 bg-aurora opacity-50" />
                <div className="relative size-7 rounded-full bg-teal-grad grid place-items-center"><Sparkles className="size-3.5" /></div>
                <div className="relative text-sm">MARK</div>
                <div className="relative ml-auto text-[11px] text-primary-foreground/60 flex items-center gap-1.5">
                  <span className="size-1.5 rounded-full bg-emerald animate-pulse-soft" /> Online
                </div>
              </div>
              <div className="p-5 space-y-4 text-sm bg-background">
                <div className="flex justify-end">
                  <div className="px-4 py-2.5 rounded-2xl rounded-br-md bg-ink text-primary-foreground max-w-[80%]">I want to take leave from Dec 23 to Jan 2</div>
                </div>
                <div className="flex gap-3">
                  <div className="size-8 rounded-full bg-ink grid place-items-center"><Sparkles className="size-3.5 text-accent-glow" /></div>
                  <div className="px-4 py-2.5 rounded-2xl rounded-bl-md bg-secondary max-w-[80%]">Of course — that's 7 working days. Your balance is 14, so you're covered. Want me to send it to Arjun for approval?</div>
                </div>
                <div className="flex gap-2 pl-11">
                  <span className="text-xs px-3 py-1.5 rounded-full bg-card border border-border">Yes, send it</span>
                  <span className="text-xs px-3 py-1.5 rounded-full bg-card border border-border">Edit dates</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Why */}
      <section id="why" className="px-6 lg:px-12 py-32 max-w-6xl mx-auto">
        <div className="max-w-2xl">
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-4">The shift</div>
          <h2 className="font-display text-5xl leading-[1.05] tracking-tight">Forms are dead. <span className="italic text-muted-foreground">Conversations work.</span></h2>
          <p className="mt-6 text-muted-foreground">Every HR system asks employees to learn its language. MARK speaks theirs. Apply for leave by saying it. Raise a concern by sharing it. Find a policy by asking.</p>
        </div>

        <div className="mt-16 grid md:grid-cols-3 gap-4">
          {[
            { icon: MessageSquare, title: "Chat is the interface", body: "No dashboards to memorize. Every action lives in conversation — across web, mobile, Slack." },
            { icon: HeartHandshake, title: "Built for humans", body: "Empathetic by default. MARK listens for tone, not just intent — and escalates to humans when it matters." },
            { icon: ShieldCheck, title: "Confidential by design", body: "Employees control what reaches HR. Sensitive conversations stay private until they choose otherwise." },
          ].map((f, i) => (
            <div key={i} className="rounded-2xl border border-border bg-card p-6 hover:shadow-elevated transition-shadow">
              <div className="size-10 rounded-xl bg-accent-soft text-accent grid place-items-center mb-4">
                <f.icon className="size-5" />
              </div>
              <div className="font-medium mb-2">{f.title}</div>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How */}
      <section id="how" className="px-6 lg:px-12 py-32 bg-secondary/40">
        <div className="max-w-6xl mx-auto">
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-4">How it works</div>
          <h2 className="font-display text-5xl leading-[1.05] tracking-tight max-w-2xl">Two people. Two views. <span className="italic text-muted-foreground">One source of truth.</span></h2>

          <div className="mt-16 grid md:grid-cols-2 gap-6">
            <div className="rounded-2xl bg-card border border-border p-8 shadow-soft">
              <div className="text-xs uppercase tracking-[0.18em] text-accent mb-4">Employees</div>
              <h3 className="font-display text-2xl mb-3">They talk. Things happen.</h3>
              <p className="text-sm text-muted-foreground">Apply for leave. Ask about insurance. Vent about a tough week. MARK handles the workflow, the policy lookup, and the empathy — in one chat.</p>
              <Link to="/employee" className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
                See the employee view <ArrowRight className="size-3.5" />
              </Link>
            </div>
            <div className="rounded-2xl bg-ink text-primary-foreground p-8 relative overflow-hidden">
              <div className="absolute inset-0 bg-aurora opacity-50" />
              <div className="relative">
                <div className="text-xs uppercase tracking-[0.18em] text-accent-glow mb-4">HR & Leadership</div>
                <h3 className="font-display text-2xl mb-3">They observe. Insights surface.</h3>
                <p className="text-sm text-primary-foreground/70">No more drowning in tickets. MARK summarizes morale, flags risk, and tells you what actually matters this week — in plain language.</p>
                <Link to="/dashboard" className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium">
                  See the HR view <ArrowRight className="size-3.5" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 lg:px-12 py-32">
        <div className="max-w-4xl mx-auto text-center">
          <Zap className="size-8 text-accent mx-auto mb-6" />
          <h2 className="font-display text-5xl leading-[1.05] tracking-tight text-balance">Stop building dashboards.<br />Start having conversations.</h2>
          <button onClick={open} className="mt-10 inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-ink text-primary-foreground text-sm font-medium shadow-elevated hover:scale-[1.02] transition-transform">
            <Sparkles className="size-4" />
            Talk to MARK
          </button>
        </div>
      </section>

      <footer className="border-t border-border px-6 lg:px-12 py-8 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-4">
        <div>© 2025 MARK · The AI HR Operating System</div>
        <div className="flex gap-6">
          <a href="#" className="hover:text-foreground">Privacy</a>
          <a href="#" className="hover:text-foreground">Security</a>
          <a href="#" className="hover:text-foreground">Contact</a>
        </div>
      </footer>
    </div>
  );
}
