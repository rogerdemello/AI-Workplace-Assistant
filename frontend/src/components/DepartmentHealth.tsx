"use client";

import { useState, useEffect } from "react";
import { getSentimentTrend, getBurnoutRisk, SentimentTrendResponse, BurnoutSummaryResponse } from "@/lib/api";
import { Activity, TrendingUp, TrendingDown, Minus } from "lucide-react";

interface DepartmentHealthProps {
  departmentId?: string;
}

interface DepartmentData {
  name: string;
  sentiment: number;
  trend: "up" | "down" | "stable";
  risk: number;
  users: number;
}

export function DepartmentHealthBenchmarks({ departmentId }: DepartmentHealthProps) {
  const [sentimentData, setSentimentData] = useState<SentimentTrendResponse[]>([]);
  const [burnoutData, setBurnoutData] = useState<BurnoutSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDepartmentData();
  }, [departmentId]);

  async function loadDepartmentData() {
    try {
      setLoading(true);
      const [sentiment, burnout] = await Promise.all([
        getSentimentTrend(30),
        getBurnoutRisk(departmentId)
      ]);
      setSentimentData(sentiment);
      setBurnoutData(burnout);
    } catch (err) {
      console.error("Failed to load department data:", err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  const departments: DepartmentData[] = [
    { name: "Engineering", sentiment: 72, trend: "up", risk: 15, users: 45 },
    { name: "Sales", sentiment: 58, trend: "down", risk: 28, users: 32 },
    { name: "Marketing", sentiment: 65, trend: "stable", risk: 18, users: 22 },
    { name: "HR", sentiment: 78, trend: "up", risk: 8, users: 12 },
    { name: "Finance", sentiment: 61, trend: "stable", risk: 22, users: 18 },
    { name: "Operations", sentiment: 54, trend: "down", risk: 35, users: 28 },
  ];

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-slate-900">Department Health Heatmap</h3>
      
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-slate-500 uppercase tracking-wider">
              <th className="pb-3 font-medium">Department</th>
              <th className="pb-3 font-medium">Sentiment Score</th>
              <th className="pb-3 font-medium">Trend</th>
              <th className="pb-3 font-medium">Burnout Risk</th>
              <th className="pb-3 font-medium">Team Size</th>
              <th className="pb-3 font-medium">Health Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {departments.map((dept) => (
              <DepartmentRow key={dept.name} department={dept} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-emerald-100 border border-emerald-300"></div>
          <span>Healthy (60+)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-amber-100 border border-amber-300"></div>
          <span>Warning (40-60)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-red-100 border border-red-300"></div>
          <span>Critical (&lt;40)</span>
        </div>
      </div>
    </div>
  );
}

function DepartmentRow({ department }: { department: DepartmentData }) {
  const getSentimentColor = (score: number) => {
    if (score >= 60) return "bg-emerald-100 text-emerald-800";
    if (score >= 40) return "bg-amber-100 text-amber-800";
    return "bg-red-100 text-red-800";
  };

  const getRiskColor = (risk: number) => {
    if (risk < 20) return "text-emerald-600";
    if (risk < 35) return "text-amber-600";
    return "text-red-600";
  };

  const TrendIcon = department.trend === "up" ? TrendingUp : department.trend === "down" ? TrendingDown : Minus;

  return (
    <tr className="hover:bg-slate-50">
      <td className="py-3 font-medium text-slate-900">{department.name}</td>
      <td className="py-3">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium ${getSentimentColor(department.sentiment)}`}>
          {department.sentiment}
        </span>
      </td>
      <td className="py-3">
        <div className="flex items-center gap-1 text-slate-600">
          <TrendIcon className={`h-4 w-4 ${
            department.trend === "up" ? "text-emerald-600" : 
            department.trend === "down" ? "text-red-600" : "text-slate-400"
          }`} />
          <span className="text-sm capitalize">{department.trend}</span>
        </div>
      </td>
      <td className="py-3">
        <span className={`text-sm font-medium ${getRiskColor(department.risk)}`}>
          {department.risk}%
        </span>
      </td>
      <td className="py-3 text-sm text-slate-600">{department.users}</td>
      <td className="py-3">
        {department.sentiment >= 60 && department.risk < 20 ? (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
            <Activity className="h-3 w-3" /> Healthy
          </span>
        ) : department.sentiment < 40 || department.risk >= 35 ? (
          <span className="inline-flex items-center gap-1 text-xs text-red-600">
            <Activity className="h-3 w-3" /> Needs Attention
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-amber-600">
            <Activity className="h-3 w-3" /> Monitor
          </span>
        )}
      </td>
    </tr>
  );
}