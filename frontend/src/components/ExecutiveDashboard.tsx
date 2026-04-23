"use client";

import { useState, useEffect } from "react";
import { 
  getExecutiveDashboard, 
  getBurnoutRisk, 
  getInsights, 
  ExecutiveDashboardResponse,
  BurnoutSummaryResponse,
  InsightResponse 
} from "@/lib/api";
import { 
  Activity, 
  AlertTriangle, 
  TrendingUp, 
  Users, 
  Lightbulb, 
  CheckCircle,
  AlertCircle
} from "lucide-react";

interface ExecutiveDashboardProps {
  onClose?: () => void;
}

export function ExecutiveDashboard({ onClose }: ExecutiveDashboardProps) {
  const [executiveData, setExecutiveData] = useState<ExecutiveDashboardResponse | null>(null);
  const [burnoutData, setBurnoutData] = useState<BurnoutSummaryResponse | null>(null);
  const [insights, setInsights] = useState<InsightResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  async function loadDashboardData() {
    try {
      setLoading(true);
      setError(null);
      
      const [exec, burnout, insightsData] = await Promise.all([
        getExecutiveDashboard(),
        getBurnoutRisk(),
        getInsights(10)
      ]);
      
      setExecutiveData(exec);
      setBurnoutData(burnout);
      setInsights(insightsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
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

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-600">{error}</p>
        <button 
          onClick={loadDashboardData}
          className="mt-2 text-sm text-red-700 underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 max-h-[80vh] overflow-y-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-slate-900">Executive Dashboard</h2>
        {onClose && (
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            ×
          </button>
        )}
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Org Health"
          value={`${executiveData?.org_health_score ?? 0}%`}
          icon={Activity}
          color="indigo"
        />
        <MetricCard
          label="Burnout Risk"
          value={`${executiveData?.burnout_risk_pct ?? 0}%`}
          icon={AlertTriangle}
          color={executiveData?.burnout_risk_pct && executiveData.burnout_risk_pct > 20 ? "red" : "green"}
        />
        <MetricCard
          label="Attrition Risk"
          value={`${executiveData?.attrition_risk_pct ?? 0}%`}
          icon={Users}
          color={executiveData?.attrition_risk_pct && executiveData.attrition_risk_pct > 30 ? "red" : "green"}
        />
        <MetricCard
          label="eNPS"
          value={String(executiveData?.enps ?? 0)}
          icon={TrendingUp}
          color="blue"
        />
      </div>

      {/* Recommendations */}
      {executiveData?.recommendations && executiveData.recommendations.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="h-5 w-5 text-amber-600" />
            <h3 className="font-semibold text-amber-800">AI Recommendations</h3>
          </div>
          <ul className="space-y-2">
            {executiveData.recommendations.map((rec, idx) => (
              <li key={idx} className="text-sm text-amber-700 flex items-start gap-2">
                <span className="text-amber-500">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Top Risks */}
      {executiveData?.top_risks && executiveData.top_risks.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <h3 className="font-semibold text-red-800">At-Risk Employees</h3>
          </div>
          <div className="space-y-2">
            {executiveData.top_risks.slice(0, 5).map((risk, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm">
                <span className="text-red-700">{risk.name}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  risk.risk_score > 0.7 ? "bg-red-200 text-red-800" : "bg-amber-200 text-amber-800"
                }`}>
                  {Math.round(risk.risk_score * 100)}% risk
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Insights */}
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <Lightbulb className="h-5 w-5 text-indigo-600" />
          <h3 className="font-semibold text-slate-900">Latest Insights</h3>
        </div>
        {insights.length > 0 ? (
          <div className="space-y-3">
            {insights.slice(0, 5).map((insight) => (
              <div 
                key={insight.id} 
                className={`p-3 rounded-lg border ${
                  insight.severity === "critical" || insight.severity === "warning"
                    ? "bg-red-50 border-red-200"
                    : insight.severity === "info"
                    ? "bg-blue-50 border-blue-200"
                    : "bg-slate-50 border-slate-200"
                }`}
              >
                <div className="flex items-start justify-between">
                  <h4 className="font-medium text-sm text-slate-900">{insight.title}</h4>
                  <span className={`px-2 py-0.5 text-xs rounded ${
                    insight.severity === "critical" ? "bg-red-200 text-red-800" :
                    insight.severity === "warning" ? "bg-amber-200 text-amber-800" :
                    "bg-blue-200 text-blue-800"
                  }`}>
                    {insight.severity}
                  </span>
                </div>
                <p className="text-sm text-slate-600 mt-1">{insight.description}</p>
                {insight.recommendations && insight.recommendations.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-slate-500">Actions:</p>
                    <ul className="text-xs text-slate-600 mt-1">
                      {insight.recommendations.slice(0, 2).map((rec, idx) => (
                        <li key={idx} className="flex items-center gap-1">
                          <CheckCircle className="h-3 w-3 text-green-500" />
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No insights available</p>
        )}
      </div>

      {/* Burnout Summary */}
      {burnoutData && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-slate-50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-slate-900">{burnoutData.high_risk_count}</p>
            <p className="text-sm text-slate-500">High Risk</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-slate-900">{burnoutData.medium_risk_count}</p>
            <p className="text-sm text-slate-500">Medium Risk</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-slate-900">
              {Math.round(burnoutData.average_risk * 100)}%
            </p>
            <p className="text-sm text-slate-500">Avg Risk</p>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ 
  label, 
  value, 
  icon: Icon, 
  color 
}: { 
  label: string; 
  value: string; 
  icon: React.ElementType; 
  color: "indigo" | "green" | "red" | "blue";
}) {
  const colorClasses = {
    indigo: "bg-indigo-50 text-indigo-600",
    green: "bg-emerald-50 text-emerald-600",
    red: "bg-red-50 text-red-600",
    blue: "bg-blue-50 text-blue-600",
  };

  return (
    <div className="bg-white rounded-xl p-4 border border-slate-200">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs text-slate-500 uppercase">{label}</p>
          <p className="text-xl font-bold text-slate-900">{value}</p>
        </div>
      </div>
    </div>
  );
}