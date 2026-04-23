"use client";

import { useMemo, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { EmployeeInsightRow } from '@/lib/hr-data';

interface EmployeeTableProps {
  rows: EmployeeInsightRow[];
}

export function EmployeeTable({ rows }: EmployeeTableProps) {
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState<'All' | 'Low' | 'Medium' | 'High'>('All');

  const filteredRows = useMemo(() => {
    const normalized = search.trim().toLowerCase();

    return rows.filter((row) => {
      const matchesSearch =
        !normalized ||
        row.name.toLowerCase().includes(normalized) ||
        row.employeeId.toLowerCase().includes(normalized) ||
        (row.department || '').toLowerCase().includes(normalized);

      const riskBand = row.riskScore >= 70 ? 'High' : row.riskScore >= 40 ? 'Medium' : 'Low';
      const matchesRisk = riskFilter === 'All' || riskBand === riskFilter;

      return matchesSearch && matchesRisk;
    });
  }, [rows, riskFilter, search]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:flex-row md:items-center md:justify-between">
        <div className="max-w-md flex-1">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search employees" className="h-11 rounded-xl bg-slate-50" />
        </div>
        <Select value={riskFilter} onValueChange={(value) => setRiskFilter(value as 'All' | 'Low' | 'Medium' | 'High')}>
          <SelectTrigger className="w-full md:w-[180px] rounded-xl">
            <SelectValue placeholder="Filter by risk" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All">All risk levels</SelectItem>
            <SelectItem value="Low">Low risk</SelectItem>
            <SelectItem value="Medium">Medium risk</SelectItem>
            <SelectItem value="High">High risk</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-4 font-semibold">Name</th>
                <th className="px-6 py-4 font-semibold">Employee ID</th>
                <th className="px-6 py-4 font-semibold">Sentiment Score</th>
                <th className="px-6 py-4 font-semibold">Risk Score</th>
                <th className="px-6 py-4 font-semibold">Last Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredRows.map((row) => {
                const riskBand = row.riskScore >= 70 ? 'High' : row.riskScore >= 40 ? 'Medium' : 'Low';

                return (
                  <tr key={row.id} className="transition-colors hover:bg-slate-50">
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-900">{row.name}</div>
                      <div className="text-xs text-slate-400">{row.department || '—'}</div>
                    </td>
                    <td className="px-6 py-4 text-slate-600">{row.employeeId}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="h-2 flex-1 rounded-full bg-slate-100">
                          <div className="h-2 rounded-full bg-blue-600" style={{ width: `${row.sentimentScore}%` }} />
                        </div>
                        <span className="w-12 text-right font-semibold text-slate-800">{row.sentimentScore}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={
                          riskBand === 'High'
                            ? 'inline-flex rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700'
                            : riskBand === 'Medium'
                              ? 'inline-flex rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700'
                              : 'inline-flex rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700'
                        }
                      >
                        {riskBand}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-600">{row.lastActive}</td>
                  </tr>
                );
              })}
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-slate-500">
                    No employees match the current search and filter.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}