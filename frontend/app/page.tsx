"use client";

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, BarChart3, Bot, FileText, Quote, Shield, Sparkles, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import ChatWidget from '@/components/ChatWidget';

const features = [
  {
    icon: Workflow,
    title: 'Smart Workflows',
    description: 'Effortlessly handle leave requests, policy queries, and HR routines through natural conversation.',
  },
  {
    icon: BarChart3,
    title: 'People Analytics',
    description: 'Access real-time engagement and risk metrics in an intuitive HR dashboard.',
  },
  {
    icon: Shield,
    title: 'Sentiment Tracking',
    description: 'Proactively monitor organizational morale and identify potential risks early.',
  }
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-slate-100 overflow-hidden font-sans selection:bg-indigo-500/30">
      {/* Dynamic Background */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-indigo-900/20 blur-[120px] mix-blend-screen" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50vw] h-[50vw] rounded-full bg-blue-900/20 blur-[120px] mix-blend-screen" />
        <div className="absolute top-[40%] left-[50%] translate-x-[-50%] w-[80vw] h-[20vw] rounded-full bg-violet-900/10 blur-[150px] mix-blend-screen" />
      </div>

      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-8">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-500 to-blue-500 text-white shadow-[0_0_20px_rgba(99,102,241,0.4)]">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-widest text-indigo-400">Mark</p>
            <p className="text-xs text-slate-400 font-medium tracking-wide">AI Chief People Officer</p>
          </div>
        </div>

        <Link href="/login">
          <Button className="rounded-full bg-white/10 hover:bg-white/20 text-white border border-white/10 backdrop-blur-md px-8 py-2 transition-all duration-300">
            Sign In
          </Button>
        </Link>
      </header>

      <main className="relative z-10 mx-auto max-w-7xl px-6 pt-20 pb-32">
        <div className="flex flex-col items-center text-center space-y-10">
          <motion.div 
            initial={{ opacity: 0, y: 30 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ duration: 0.7, ease: "easeOut" }}
            className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-5 py-2.5 text-sm font-medium text-indigo-300 backdrop-blur-md"
          >
            <Sparkles className="h-4 w-4" />
            The Future of Employee Experience
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, y: 30 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ duration: 0.7, delay: 0.1, ease: "easeOut" }}
            className="space-y-6 max-w-4xl"
          >
            <h1 className="text-6xl sm:text-7xl lg:text-8xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-white via-slate-200 to-slate-500 pb-2">
              Meet Your AI <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">People Officer.</span>
            </h1>
            <p className="mx-auto max-w-2xl text-xl leading-relaxed text-slate-400 font-light">
              Transform your HR operations with Mark. Automate workflows, understand employee sentiment, and resolve tickets instantly — all through a simple conversational interface.
            </p>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, y: 30 }} 
            animate={{ opacity: 1, y: 0 }} 
            transition={{ duration: 0.7, delay: 0.2, ease: "easeOut" }}
            className="pt-4"
          >
            <Link href="/login">
              <Button size="lg" className="h-14 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white px-10 text-lg shadow-[0_0_30px_rgba(79,70,229,0.4)] transition-all duration-300 hover:shadow-[0_0_40px_rgba(79,70,229,0.6)] group">
                Get Started
                <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </Button>
            </Link>
          </motion.div>
        </div>

        <motion.div 
          initial={{ opacity: 0, y: 40 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }}
          className="mt-32 grid gap-6 sm:grid-cols-3 max-w-5xl mx-auto"
        >
          {features.map((feature, idx) => (
            <Card key={feature.title} className="border-white/5 bg-white/5 backdrop-blur-xl hover:bg-white/10 transition-all duration-500 group">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-400 group-hover:scale-110 transition-transform duration-500">
                  <feature.icon className="h-6 w-6" />
                </div>
                <CardTitle className="text-lg font-semibold text-white tracking-wide">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm leading-relaxed text-slate-400">
                {feature.description}
              </CardContent>
            </Card>
          ))}
        </motion.div>
      </main>

      {/* Floating Chatbot */}
      <ChatWidget />
    </div>
  );
}
