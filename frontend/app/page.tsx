"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { 
  Workflow, 
  BarChart3, 
  Ticket, 
  FileText, 
  Heart, 
  MessageCircle 
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const features = [
  {
    icon: Workflow,
    title: "Smart Workflows",
    description: "Automate HR processes with intelligent workflows that handle leave requests, onboarding, and more."
  },
  {
    icon: BarChart3,
    title: "People Analytics",
    description: "Data-driven insights into workforce trends, engagement metrics, and performance indicators."
  },
  {
    icon: Ticket,
    title: "Ticketing System",
    description: "Track and resolve employee issues efficiently with AI-powered prioritization."
  },
  {
    icon: FileText,
    title: "Document AI",
    description: "Search and summarize HR policies, handbooks, and documentation instantly."
  },
  {
    icon: Heart,
    title: "Sentiment Tracking",
    description: "Monitor team morale through pulse surveys and communication analysis."
  },
  {
    icon: MessageCircle,
    title: "Proactive Check-ins",
    description: "AI-driven nudges to managers for timely one-on-ones and team check-ins."
  }
]

const chatMessages = [
  { role: "user", content: "How do I request time off?" },
  { role: "assistant", content: "You can request time off by going to the leave section or just tell me your dates and I'll help you submit a request!" }
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <nav className="container mx-auto px-6 py-4 flex items-center justify-between">
        <div className="text-2xl font-bold text-slate-900">
          <span className="text-blue-600">Infeedo</span> AI
        </div>
        <div className="hidden md:flex items-center gap-6">
          <Link href="#features" className="text-slate-600 hover:text-slate-900 transition-colors">
            Features
          </Link>
          <Link href="#demo" className="text-slate-600 hover:text-slate-900 transition-colors">
            Demo
          </Link>
          <Link href="/chat">
            <Button variant="default" size="sm">
              Try the Assistant
            </Button>
          </Link>
        </div>
      </nav>

      <section className="container mx-auto px-6 py-16 md:py-24">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-slate-900 leading-tight mb-6">
              Your AI{" "}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600">
                Chief People Officer
              </span>
            </h1>
            <p className="text-lg md:text-xl text-slate-600 mb-8 leading-relaxed">
              The intelligent HR assistant that helps employees with policies, 
              workflows, and analytics — all through natural conversation.
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Link href="/chat">
                <Button size="lg" className="w-full sm:w-auto bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700">
                  Try the assistant
                </Button>
              </Link>
              <Button size="lg" variant="outline" className="w-full sm:w-auto">
                View demo
              </Button>
            </div>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="relative"
            id="demo"
          >
            <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
              <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                    <span className="text-white font-semibold">AI</span>
                  </div>
                  <div>
                    <h3 className="text-white font-semibold">HR Assistant</h3>
                    <p className="text-white/70 text-sm">Always here to help</p>
                  </div>
                </div>
              </div>
              
              <div className="p-4 space-y-4">
                {chatMessages.map((msg, idx) => (
                  <div 
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div 
                      className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                        msg.role === 'user' 
                          ? 'bg-blue-600 text-white rounded-br-md' 
                          : 'bg-slate-100 text-slate-800 rounded-bl-md'
                      }`}
                    >
                      <p className="text-sm">{msg.content}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-4 border-t border-slate-100">
                <div className="flex items-center gap-3 bg-slate-50 rounded-full px-4 py-3">
                  <span className="text-slate-400">Type a message...</span>
                </div>
              </div>
            </div>

            <div className="absolute -top-4 -right-4 w-24 h-24 bg-blue-100 rounded-full opacity-50" />
            <div className="absolute -bottom-4 -left-4 w-16 h-16 bg-purple-100 rounded-full opacity-50" />
          </motion.div>
        </div>
      </section>

      <section className="bg-slate-50 py-16 md:py-24" id="features">
        <div className="container mx-auto px-6">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Powerful HR Features
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Everything you need to transform your HR operations with AI-powered intelligence.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
              >
                <Card className="h-full hover:shadow-lg transition-shadow duration-300 border-slate-200">
                  <CardHeader>
                    <div className="w-12 h-12 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl flex items-center justify-center mb-4">
                      <feature.icon className="w-6 h-6 text-white" />
                    </div>
                    <CardTitle className="text-xl">{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-base">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-24">
        <div className="container mx-auto px-6">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-3xl p-8 md:p-12 text-center"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Ready to transform your HR?
            </h2>
            <p className="text-lg text-white/80 mb-8 max-w-2xl mx-auto">
              Start with our AI assistant today and see the difference intelligent HR can make.
            </p>
            <Link href="/chat">
              <Button 
                size="lg" 
                className="bg-white text-blue-600 hover:bg-slate-100 font-semibold px-8"
              >
                Try the assistant
              </Button>
            </Link>
          </motion.div>
        </div>
      </section>

      <footer className="bg-slate-900 py-8">
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-white font-semibold text-xl">
              <span className="text-blue-400">Infeedo</span> AI
            </div>
            <p className="text-slate-400 text-sm">
              © 2024 Infeedo AI. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}