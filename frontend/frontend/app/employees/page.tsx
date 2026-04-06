"use client";

import { useState } from "react";
import { Search, Filter, MoreHorizontal, User, AlertCircle, ShieldAlert } from "lucide-react";

interface Employee {
  id: string;
  name: string;
  department: string;
  sentiment: number;
  risk: "Low" | "Medium" | "High";
  lastActive: string;
}

const mockEmployees: Employee[] = [
  { id: "EMP-001", name: "Sarah Connor", department: "Engineering", sentiment: 85, risk: "Low", lastActive: "10 mins ago" },
  { id: "EMP-002", name: "John Smith", department: "Sales", sentiment: 42, risk: "High", lastActive: "2 hours ago" },
  { id: "EMP-003", name: "Emily Chen", department: "Marketing", sentiment: 78, risk: "Low", lastActive: "Just now" },
  { id: "EMP-004", name: "Michael Chang", department: "Engineering", sentiment: 55, risk: "Medium", lastActive: "1 day ago" },
  { id: "EMP-005", name: "Jessica Davis", department: "HR", sentiment: 92, risk: "Low", lastActive: "5 mins ago" },
  { id: "EMP-006", name: "Robert Wilson", department: "Sales", sentiment: 48, risk: "High", lastActive: "3 days ago" },
  { id: "EMP-007", name: "David Miller", department: "Product", sentiment: 65, risk: "Medium", lastActive: "1 hour ago" },
];

export default function EmployeesPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [riskFilter, setRiskFilter] = useState<string>("All");

  const filteredEmployees = mockEmployees.filter(emp => {
    const matchesSearch = emp.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          emp.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRisk = riskFilter === "All" || emp.risk === riskFilter;
    return matchesSearch && matchesRisk;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">People Directory</h1>
          <p className="text-sm text-slate-500 mt-1">Manage and monitor employee wellbeing.</p>
        </div>
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shadow">
          Add Employee
        </button>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-center bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="relative w-full sm:w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
          <input 
            type="text" 
            placeholder="Search by name or ID..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
        </div>
        
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="text-slate-400 w-4 h-4 ml-2 sm:ml-0" />
          <select 
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="w-full sm:w-auto px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-slate-700"
          >
            <option value="All">All Risks</option>
            <option value="Low">Low Risk</option>
            <option value="Medium">Medium Risk</option>
            <option value="High">High Risk</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-slate-500 border-b border-slate-200 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-4 font-semibold">Employee</th>
                <th className="px-6 py-4 font-semibold">Department</th>
                <th className="px-6 py-4 font-semibold">Sentiment Score</th>
                <th className="px-6 py-4 font-semibold">Attrition Risk</th>
                <th className="px-6 py-4 font-semibold">Last Active</th>
                <th className="px-6 py-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredEmployees.map((emp) => (
                <tr key={emp.id} className="hover:bg-slate-50 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                        <User className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="font-medium text-slate-900">{emp.name}</div>
                        <div className="text-xs text-slate-400">{emp.id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-medium">
                      {emp.department}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-full bg-slate-100 rounded-full h-2 min-w-[60px]">
                        <div 
                          className={`h-2 rounded-full ${emp.sentiment > 70 ? 'bg-green-500' : emp.sentiment > 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${emp.sentiment}%` }}
                        ></div>
                      </div>
                      <span className="font-medium">{emp.sentiment}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                      emp.risk === 'Low' ? 'bg-green-50 text-green-700 border border-green-200' : 
                      emp.risk === 'Medium' ? 'bg-amber-50 text-amber-700 border border-amber-200' : 
                      'bg-red-50 text-red-700 border border-red-200'
                    }`}>
                      {emp.risk === 'High' && <ShieldAlert className="w-3.5 h-3.5" />}
                      {emp.risk === 'Medium' && <AlertCircle className="w-3.5 h-3.5" />}
                      {emp.risk}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-slate-500">{emp.lastActive}</td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-slate-400 hover:text-blue-600 transition-colors opacity-0 group-hover:opacity-100 p-1">
                      <MoreHorizontal className="w-5 h-5" />
                    </button>
                  </td>
                </tr>
              ))}
              {filteredEmployees.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    No employees found matching your criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
