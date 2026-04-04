'use client'

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Search } from 'lucide-react'

interface Employee {
  id: string
  name: string
  sentimentScore: number
  riskScore: 'Low' | 'Medium' | 'High'
  lastActive: string
  status: 'Normal' | 'At Risk'
  email: string
  department: string
}

const mockEmployees: Employee[] = [
  { id: '1', name: 'John Doe', sentimentScore: 85, riskScore: 'Low', lastActive: '2 hours ago', status: 'Normal', email: 'john.doe@company.com', department: 'Engineering' },
  { id: '2', name: 'Jane Smith', sentimentScore: 45, riskScore: 'High', lastActive: '1 week ago', status: 'At Risk', email: 'jane.smith@company.com', department: 'Sales' },
  { id: '3', name: 'Michael Johnson', sentimentScore: 72, riskScore: 'Low', lastActive: '30 minutes ago', status: 'Normal', email: 'michael.j@company.com', department: 'Marketing' },
  { id: '4', name: 'Emily Davis', sentimentScore: 38, riskScore: 'High', lastActive: '3 days ago', status: 'At Risk', email: 'emily.davis@company.com', department: 'HR' },
  { id: '5', name: 'David Wilson', sentimentScore: 68, riskScore: 'Medium', lastActive: '5 hours ago', status: 'Normal', email: 'david.w@company.com', department: 'Operations' },
  { id: '6', name: 'Sarah Brown', sentimentScore: 91, riskScore: 'Low', lastActive: '1 hour ago', status: 'Normal', email: 'sarah.b@company.com', department: 'Engineering' },
  { id: '7', name: 'James Taylor', sentimentScore: 55, riskScore: 'Medium', lastActive: '2 days ago', status: 'Normal', email: 'james.t@company.com', department: 'Sales' },
  { id: '8', name: 'Lisa Anderson', sentimentScore: 32, riskScore: 'High', lastActive: '1 week ago', status: 'At Risk', email: 'lisa.a@company.com', department: 'Marketing' },
  { id: '9', name: 'Robert Martinez', sentimentScore: 78, riskScore: 'Low', lastActive: '4 hours ago', status: 'Normal', email: 'robert.m@company.com', department: 'Finance' },
  { id: '10', name: 'Jennifer Lee', sentimentScore: 62, riskScore: 'Medium', lastActive: '6 hours ago', status: 'Normal', email: 'jennifer.l@company.com', department: 'HR' },
]

const riskLevels = ['All', 'Low', 'Medium', 'High']

export default function EmployeesPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [riskFilter, setRiskFilter] = useState('All')

  const filteredEmployees = mockEmployees.filter((employee) => {
    const matchesSearch = 
      employee.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      employee.id.toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesRisk = riskFilter === 'All' || employee.riskScore === riskFilter
    
    return matchesSearch && matchesRisk
  })

  const getStatusBadge = (status: Employee['status']) => {
    if (status === 'Normal') {
      return <Badge className="bg-green-500 hover:bg-green-600">Normal</Badge>
    }
    return <Badge variant="destructive">At Risk</Badge>
  }

  const getRiskBadge = (risk: Employee['riskScore']) => {
    if (risk === 'Low') {
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Low</span>
    }
    if (risk === 'Medium') {
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">Medium</span>
    }
    return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">High</span>
  }

  const getSentimentColor = (score: number) => {
    if (score >= 70) return 'text-green-600'
    if (score >= 50) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="container mx-auto py-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <h1 className="text-2xl font-bold">Employee Directory</h1>
        
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by name or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 border rounded-md w-[200px] focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          
          <Select value={riskFilter} onValueChange={setRiskFilter}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Risk Level" />
            </SelectTrigger>
            <SelectContent>
              {riskLevels.map((level) => (
                <SelectItem key={level} value={level}>{level}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Name</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">ID</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Sentiment Score</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Risk Score</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Last Active</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredEmployees.map((employee) => (
              <tr 
                key={employee.id} 
                className="hover:bg-muted/50 transition-colors cursor-pointer"
              >
                <td className="px-4 py-3">
                  <div className="font-medium">{employee.name}</div>
                  <div className="text-sm text-muted-foreground">{employee.email}</div>
                </td>
                <td className="px-4 py-3 text-sm">{employee.id}</td>
                <td className="px-4 py-3">
                  <span className={`font-medium ${getSentimentColor(employee.sentimentScore)}`}>
                    {employee.sentimentScore}%
                  </span>
                </td>
                <td className="px-4 py-3">{getRiskBadge(employee.riskScore)}</td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{employee.lastActive}</td>
                <td className="px-4 py-3">{getStatusBadge(employee.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {filteredEmployees.length === 0 && (
          <div className="flex items-center justify-center h-32 text-muted-foreground">
            No employees found matching your search criteria.
          </div>
        )}
      </div>
      
      <div className="mt-4 text-sm text-muted-foreground">
        Showing {filteredEmployees.length} of {mockEmployees.length} employees
      </div>
    </div>
  )
}
