"use client";

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import type { SentimentPoint } from '@/lib/hr-data';

interface SentimentChartProps {
  data: SentimentPoint[];
}

export function SentimentChart({ data }: SentimentChartProps) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle>Sentiment Over Time</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} tickFormatter={(value) => new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} />
              <YAxis tick={{ fill: '#64748b', fontSize: 12 }} />
              <Tooltip
                contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0', boxShadow: '0 10px 20px rgba(15, 23, 42, 0.08)' }}
                formatter={(value, name) => [`${value}%`, name]}
                labelFormatter={(value) => new Date(String(value)).toLocaleDateString()}
              />
              <Legend />
              <Line type="monotone" dataKey="positive" stroke="#2563eb" strokeWidth={3} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="neutral" stroke="#64748b" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="negative" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}