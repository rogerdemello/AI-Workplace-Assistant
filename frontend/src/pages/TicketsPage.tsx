import { useState, useMemo } from 'react'
import { TicketList } from '@/components/tickets/TicketList'
import { TicketDetail } from '@/components/tickets/TicketDetail'
import { TicketForm } from '@/components/tickets/TicketForm'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'

interface Ticket {
  id: string
  query: string
  category: string
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  priority: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
}

type StatusFilter = 'all' | 'open' | 'in_progress' | 'resolved' | 'closed'
type PriorityFilter = 'all' | 'low' | 'medium' | 'high' | 'critical'

// Sample data for demonstration
const sampleTickets: Ticket[] = [
  {
    id: '1',
    query: 'How do I apply for sick leave?',
    category: 'leave',
    status: 'open',
    priority: 'medium',
    created_at: '2026-03-25T10:00:00Z'
  },
  {
    id: '2',
    query: 'What are the health insurance benefits?',
    category: 'benefits',
    status: 'in_progress',
    priority: 'high',
    created_at: '2026-03-24T14:30:00Z'
  },
  {
    id: '3',
    query: 'When will my payroll be processed?',
    category: 'payroll',
    status: 'resolved',
    priority: 'low',
    created_at: '2026-03-20T09:15:00Z'
  },
  {
    id: '4',
    query: 'Need clarification on remote work policy',
    category: 'general',
    status: 'closed',
    priority: 'medium',
    created_at: '2026-03-15T16:45:00Z'
  }
]

export function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>(sampleTickets)
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)
  const [showForm, setShowForm] = useState(false)
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all')

  // Filtered tickets
  const filteredTickets = useMemo(() => {
    return tickets.filter(ticket => {
      const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter
      const matchesPriority = priorityFilter === 'all' || ticket.priority === priorityFilter
      return matchesStatus && matchesPriority
    })
  }, [tickets, statusFilter, priorityFilter])

  const handleCreateTicket = (data: { query: string; category: string; priority: string }) => {
    const newTicket: Ticket = {
      id: Date.now().toString(),
      query: data.query,
      category: data.category,
      priority: data.priority as Ticket['priority'],
      status: 'open',
      created_at: new Date().toISOString()
    }
    setTickets([newTicket, ...tickets])
    setShowForm(false)
  }

  const handleStatusUpdate = (ticketId: string, newStatus: string) => {
    const updatedStatus = newStatus as Ticket['status']
    setTickets(tickets.map(ticket => 
      ticket.id === ticketId ? { ...ticket, status: updatedStatus } : ticket
    ))
    
    // Update selected ticket if it's the one being modified
    if (selectedTicket?.id === ticketId) {
      setSelectedTicket({ ...selectedTicket, status: updatedStatus })
    }
  }

  const handleSelectTicket = (id: string) => {
    const ticket = tickets.find(t => t.id === id) || null
    setSelectedTicket(ticket)
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Support Tickets</h1>
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'New Ticket'}
        </Button>
      </div>

      {/* Create Form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New Ticket</CardTitle>
          </CardHeader>
          <CardContent>
            <TicketForm 
              onSubmit={handleCreateTicket} 
              onCancel={() => setShowForm(false)} 
            />
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="space-y-2">
              <Label htmlFor="status-filter">Status</Label>
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
                <SelectTrigger id="status-filter" className="w-[160px]">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="priority-filter">Priority</Label>
              <Select value={priorityFilter} onValueChange={(v) => setPriorityFilter(v as PriorityFilter)}>
                <SelectTrigger id="priority-filter" className="w-[160px]">
                  <SelectValue placeholder="Filter by priority" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Priorities</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="text-sm text-muted-foreground pb-2">
              Showing {filteredTickets.length} of {tickets.length} tickets
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Ticket List */}
        <div>
          <h2 className="text-lg font-semibold mb-3">Your Tickets</h2>
          <TicketList 
            tickets={filteredTickets} 
            onSelect={handleSelectTicket} 
          />
        </div>

        {/* Ticket Detail */}
        <div>
          {selectedTicket ? (
            <TicketDetail 
              ticket={selectedTicket} 
              onClose={() => setSelectedTicket(null)}
              onStatusUpdate={handleStatusUpdate}
            />
          ) : (
            <Card className="h-fit">
              <CardContent className="py-12 text-center text-muted-foreground">
                Select a ticket to view details
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
