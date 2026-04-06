"use client";

import { motion } from "framer-motion";
import { MessageSquare, Activity, FileText, Bot, Shield, Zap, ArrowRight, UserCheck } from "lucide-react";
import Link from "next/link";
import ChatWidget from "@/components/ChatWidget";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50 selection:bg-blue-200">
      {/* Navbar Placeholder */}
      <nav className="flex items-center justify-between p-6 max-w-7xl mx-auto">
        <div className="flex items-center space-x-2">
          <Bot className="w-8 h-8 text-blue-600" />
          <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">Mark AI</span>
        </div>
        <div className="space-x-4 hidden md:flex items-center">
          <a href="#features" className="text-sm font-medium text-slate-600 hover:text-blue-600 transition">Features</a>
          <a href="#demo" className="text-sm font-medium text-slate-600 hover:text-blue-600 transition">Demo</a>
          <Link href="/dashboard" className="px-4 py-2 text-sm font-medium border border-slate-200 rounded-lg hover:border-slate-300 transition-colors">
            Login
          </Link>
          <Link href="/dashboard" className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg shadow-md hover:bg-blue-700 hover:shadow-lg transition-all flex items-center">
            Open App <ArrowRight className="ml-1 w-4 h-4" />
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-6 py-20 md:py-32 grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="space-y-8"
        >
          <div className="inline-flex items-center px-3 py-1 rounded-full bg-blue-50 text-blue-600 text-sm font-medium border border-blue-100 mb-2">
            <Sparkles className="w-4 h-4 mr-2" />
            Introducing the Future of HR
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight leading-tight">
            Meet Your <span className="bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">AI Chief People Officer</span>
          </h1>
          <p className="text-lg md:text-xl text-slate-600 leading-relaxed max-w-lg">
            Mark connects deeply with your employees, uncovers true sentiment, automates complex workflows, and prevents attrition before it happens.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 pt-4">
            <button 
              className="px-8 py-4 bg-slate-900 text-white rounded-xl font-semibold shadow-xl hover:shadow-2xl hover:bg-slate-800 hover:-translate-y-0.5 transition-all flex items-center justify-center gap-2"
              onClick={() => {
                const btn = document.querySelector('.fixed.bottom-6.right-6');
                if (btn) (btn as HTMLButtonElement).click();
              }}
            >
              <MessageSquare className="w-5 h-5" />
              Chat with Mark
            </button>
            <Link href="/dashboard" className="px-8 py-4 bg-white text-slate-900 rounded-xl font-semibold shadow-sm border border-slate-200 hover:bg-slate-50 transition-all flex items-center justify-center gap-2">
              <Activity className="w-5 h-5 text-slate-400" />
              View Dashboard
            </Link>
          </div>
        </motion.div>

        {/* Mock Chat Preview */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="relative h-[600px] w-full hidden md:block"
        >
          <div className="absolute inset-0 bg-gradient-to-tr from-blue-100 to-cyan-50 rounded-3xl transform rotate-3 scale-105 opacity-50 blur-xl"></div>
          <div className="relative bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden h-full flex flex-col z-10 w-4/5 ml-auto">
            {/* App Window Header */}
            <div className="h-12 border-b border-slate-100 bg-slate-50/80 flex items-center px-4 backdrop-blur-md">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400"></div>
                <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                <div className="w-3 h-3 rounded-full bg-green-400"></div>
              </div>
              <div className="mx-auto text-xs font-medium text-slate-400 flex items-center gap-1">
                <Shield className="w-3 h-3" /> Secure Chat
              </div>
            </div>
            {/* Fake Chat Content */}
            <div className="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50/30">
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-xs shadow-sm mt-1">A</div>
                <div className="bg-white p-4 text-sm rounded-2xl rounded-tl-none shadow-sm border border-slate-100 text-slate-700 max-w-[85%]">
                  Hi Alex! It's been 6 months since you joined engineering. How are you feeling about work lately? ���
                </div>
              </div>
              <div className="flex items-start gap-4 flex-row-reverse">
                <div className="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-xs shadow-sm mt-1">AX</div>
                <div className="bg-slate-800 text-white p-4 text-sm rounded-2xl rounded-tr-none shadow-sm max-w-[85%]">
                  Honestly, I've been feeling a bit overwhelmed. The new release deadline is super tight.
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-xs shadow-sm mt-1">A</div>
                <div className="bg-white p-4 text-sm rounded-2xl rounded-tl-none shadow-sm border border-blue-100 border-l-4 border-l-blue-500 text-slate-700 max-w-[85%]">
                  That sounds frustrating ��� <br/><br/>
                  I can see you've been working late. Would you like me to suggest a quick 1-on-1 block with your manager to recalibrate the timeline?
                </div>
              </div>
            </div>
            <div className="h-16 border-t border-slate-100 bg-white flex items-center px-4">
              <div className="w-full h-10 bg-slate-100 rounded-full border border-slate-200"></div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Features Grid */}
      <section id="features" className="bg-white py-24 border-t border-slate-100">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">Everything an HR Team Needs</h2>
            <p className="text-slate-500">Mark seamlessly blends natural conversation with powerful enterprise capabilities.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              { icon: MessageSquare, title: "Smart Workflows", desc: "Automate leave requests, policy lookups, and grievance reporting through chat." },
              { icon: Activity, title: "Sentiment Tracking", desc: "Continuous pulse-checks to measure team morale and predict burnout." },
              { icon: Shield, title: "Ticketing System", desc: "Intelligent triage that categorizes and routes issues to the right department." },
              { icon: FileText, title: "Document AI", desc: "Instant answers from company handbooks, benefit guides, and policies." },
              { icon: UserCheck, title: "Proactive Check-ins", desc: "Reaches out at critical points (onboarding, anniversaries) to gather feedback." },
              { icon: Zap, title: "People Analytics", desc: "Beautiful dashboards bridging the gap between raw data and executable HR strategy." },
            ].map((Feature, i) => (
              <motion.div 
                key={i}
                whileHover={{ y: -5 }}
                className="p-8 rounded-2xl bg-slate-50 border border-slate-100 hover:border-blue-200 hover:shadow-lg transition-all"
              >
                <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center mb-6">
                  <Feature.icon className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">{Feature.title}</h3>
                <p className="text-slate-600 leading-relaxed text-sm">
                  {Feature.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="py-24 bg-slate-900 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900 via-slate-900 to-slate-900 opacity-50"></div>
        <div className="max-w-4xl mx-auto px-6 relative z-10 text-center">
          <h2 className="text-4xl font-bold text-white mb-6">Ready to empower your workforce?</h2>
          <p className="text-slate-300 mb-10 text-lg">Join forward-thinking companies using AI to drive engagement.</p>
          <button 
            className="px-8 py-4 bg-blue-600 text-white rounded-xl font-semibold shadow-lg hover:bg-blue-500 hover:shadow-blue-500/25 transition-all text-lg"
            onClick={() => {
              const btn = document.querySelector('.fixed.bottom-6.right-6');
              if (btn) (btn as HTMLButtonElement).click();
            }}
          >
            Open Assistant
          </button>
        </div>
      </section>
      
      {/* We inject Chat Widget here too if it's not rendered via layout globally.
          Wait, it IS rendered in layout.tsx globally, so we don't need it here.
          But the layout applies to page.tsx, so we are good. */}
    </div>
  );
}

// Quick tiny helper for the spark icon needed above
function Sparkles(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinelinejoin="round">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
      <path d="M5 3v4"/>
      <path d="M19 17v4"/>
      <path d="M3 5h4"/>
      <path d="M17 19h4"/>
    </svg>
  );
}
