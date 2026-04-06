"use client";

import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";
import { Users, Ticket, HeartPulse, Sparkles } from "lucide-react";

const sentimentData = [
  { name: "Mon", score: 65 },
  { name: "Tue", score: 70 },
  { name: "Wed", score: 68 },
  { name: "Thu", score: 75 },
  { name: "Fri", score: 85 },
  { name: "Sat", score: 82 },
  { name: "Sun", score: 88 },
];

const ticketData = [
  { category: "Leave", count: 24 },
  { category: "Payroll", count: 13 },
  { category: "Hardware", count: 8 },
  { category: "Policy", count: 19 },
];

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Overview</h1>
        <button className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800 transition-colors shadow">
          Download Report
        </button>
      </div>

      {/* Top Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Engagement Score</p>
            <h3 className="text-3xl font-bold text-slate-900 mt-2">78%</h3>
            <p className="text-xs text-green-600 mt-1 font-medium">+2.4% from last month</p>
          </div>
          <div className="p-3 bg-blue-50 rounded-xl text-blue-600">
            <HeartPulse size={24} />
          </div>
        </div>

        <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Risk Level</p>
            <h3 className="text-3xl font-bold text-amber-500 mt-2">Medium</h3>
            <p className="text-xs text-slate-500 mt-1">12 employees at risk</p>
          </div>
          <div className="p-3 bg-amber-50 rounded-xl text-amber-600">
            <Users size={24} />
          </div>
        </div>

        <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Open Tickets</p>
            <h3 className="text-3xl font-bold text-slate-900 mt-2">64</h3>
            <p className="text-xs text-red-500 mt-1 font-medium">8 high priority</p>
          </div>
          <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600">
            <Ticket size={24} />
          </div>
        </div>
      </div>

      {/* AI Insight */}
      <div className="p-5 bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-100 rounded-2xl flex items-start space-x-4">
        <div className="p-2 bg-white rounded-full text-blue-600 shadow-sm">
          <Sparkles size={20} />
        </div>
        <div>
          <h4 className="text-blue-900 font-semibold text-sm">Mark Insight</h4>
          <p className="text-blue-800 text-sm mt-1 leading-relaxed">
            Overall sentiment is trending upwards this week. However, there is a spike in tickets related to "Payroll" in the Engineering department. Consider sending a proactive announcement clarifying the recent tax deduction updates.
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col">
          <h3 className="text-lg font-semibold text-slate-800 mb-6">Sentiment Over Time</h3>
          <div className="h-64 w-full flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sentimentData}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} dx={-10} />
                <Tooltip 
                  contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  itemStyle={{ color: '#0f172a', fontWeight: 500 }}
                />
                <Area type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorScore)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col">
          <h3 className="text-lg font-semibold text-slate-800 mb-6">Tickets by Category</h3>
          <div className="h-64 w-full flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ticketData} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} />
                <YAxis dataKey="category" type="category" axisLine={false} tickLine={false} tick={{fill: '#475569', fontSize: 13, fontWeight: 500}} width={80} />
                <Tooltip 
                  cursor={{fill: '#f8fafc'}}
                  contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Bar dataKey="count" fill="#0ea5e9" radius={[0, 4, 4, 0]} barSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
