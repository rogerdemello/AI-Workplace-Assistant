'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { getAnalyticsOverview, getSentimentTrend, SentimentTrendResponse } from '@/lib/api'

interface KPI {
  label: string
  value: string
  change: string
  positive: boolean
}

const departments = ['All Departments', 'Engineering', 'Sales', 'Marketing', 'HR', 'Operations']
const dateRanges = ['Last 7 days', 'Last 30 days', 'Last 90 days', 'Last year']

export default function DashboardPage() {
  const [department, setDepartment] = useState('All Departments')
  const [dateRange, setDateRange] = useState('Last 30 days')
  const [kpis, setKpis] = useState<KPI[]>([])
  const [sentimentData, setSentimentData] = useState<{ month: string; positive: number; neutral: number; negative: number }[]>([])
  const [resolutionData, setResolutionData] = useState<{ priority: string; rate: number; fill: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      
      try {
        const [overview, sentiment] = await Promise.all([
          getAnalyticsOverview(),
          getSentimentTrend(30)
        ])

        setKpis([
          { label: 'Engagement Score', value: `${overview.engagement_score}%`, change: '', positive: true },
          { label: 'Resolution Rate', value: `${Math.round(overview.resolution_rate * 100)}%`, change: '', positive: true },
          { label: 'Avg Response', value: `${overview.avg_response_time}h`, change: '', positive: true },
          { label: 'Active Users', value: String(overview.active_users), change: '', positive: true }
        ])

        const last6Months = sentiment.slice(-6).map((item: SentimentTrendResponse) => {
          const date = new Date(item.date)
          return {
            month: date.toLocaleString('default', { month: 'short' }),
            positive: item.positive,
            neutral: item.neutral,
            negative: item.negative
          }
        })
        setSentimentData(last6Months)

        setResolutionData([
          { priority: 'Critical', rate: 95, fill: 'hsl(0 84.2% 60.2%)' },
          { priority: 'High', rate: 88, fill: 'hsl(25 95.4% 53.3%)' },
          { priority: 'Medium', rate: 75, fill: 'hsl(48 96.5% 53.3%)' },
          { priority: 'Low', rate: 60, fill: 'hsl(142 76.2% 36.3%)' }
        ])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
        setKpis([
          { label: 'Engagement Score', value: 'N/A', change: '', positive: true },
          { label: 'Resolution Rate', value: 'N/A', change: '', positive: true },
          { label: 'Avg Response', value: 'N/A', change: '', positive: true },
          { label: 'Active Users', value: 'N/A', change: '', positive: true }
        ])
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading dashboard...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-red-500">Error: {error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <h1 className="text-2xl font-bold">HR Analytics Dashboard</h1>
        
        <div className="flex flex-col sm:flex-row gap-3">
          <Select value={department} onValueChange={setDepartment}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Department" />
            </SelectTrigger>
            <SelectContent>
              {departments.map((dept) => (
                <SelectItem key={dept} value={dept}>{dept}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select value={dateRange} onValueChange={setDateRange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Date Range" />
            </SelectTrigger>
            <SelectContent>
              {dateRanges.map((range) => (
                <SelectItem key={range} value={range}>{range}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {kpis.map((kpi, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{kpi.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{kpi.value}</div>
              <Badge variant={kpi.positive ? 'default' : 'destructive'} className="mt-1">
                {kpi.change}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Sentiment Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sentimentData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(214.3 31.8% 91.4%)" />
                  <XAxis dataKey="month" stroke="hsl(215.4 16.3% 46.9%)" fontSize={12} />
                  <YAxis stroke="hsl(215.4 16.3% 46.9%)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(0 0% 100%)',
                      border: '1px solid hsl(214.3 31.8% 91.4%)',
                      borderRadius: '8px'
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="positive"
                    stroke="hsl(142 76.2% 36.3%)"
                    strokeWidth={2}
                    dot={{ fill: 'hsl(142 76.2% 36.3%)', r: 4 }}
                    name="Positive"
                  />
                  <Line
                    type="monotone"
                    dataKey="neutral"
                    stroke="hsl(221.2 83.2% 53.3%)"
                    strokeWidth={2}
                    dot={{ fill: 'hsl(221.2 83.2% 53.3%)', r: 4 }}
                    name="Neutral"
                  />
                  <Line
                    type="monotone"
                    dataKey="negative"
                    stroke="hsl(0 84.2% 60.2%)"
                    strokeWidth={2}
                    dot={{ fill: 'hsl(0 84.2% 60.2%)', r: 4 }}
                    name="Negative"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Resolution by Priority</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={resolutionData} layout="vertical" margin={{ top: 5, right: 20, left: 40, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(214.3 31.8% 91.4%)" />
                  <XAxis type="number" domain={[0, 100]} stroke="hsl(215.4 16.3% 46.9%)" fontSize={12} />
                  <YAxis type="category" dataKey="priority" stroke="hsl(215.4 16.3% 46.9%)" fontSize={12} width={60} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(0 0% 100%)',
                      border: '1px solid hsl(214.3 31.8% 91.4%)',
                      borderRadius: '8px'
                    }}
                    formatter={(value) => [`${value}%`, 'Resolution Rate']}
                  />
                  <Bar dataKey="rate" name="Resolution Rate" radius={[0, 4, 4, 0]}>
                    {resolutionData.map((entry, index) => (
                      <Bar key={`bar-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
