'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { TicketList } from '@/components/tickets/TicketList'
import { TicketDetail } from '@/components/tickets/TicketDetail'
import { TicketForm } from '@/components/tickets/TicketForm'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { getTickets, createTicket, updateTicket } from '@/lib/api'

interface Ticket {
  id: string
  query: string
  category: string
  status: 'open' | 'in_progress' | 'resolved' | 'escalated' | 'closed'
  priority: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
}

type StatusFilter = 'all' | 'open' | 'in_progress' | 'resolved' | 'closed'
type PriorityFilter = 'all' | 'low' | 'medium' | 'high' | 'critical'

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all')

  const fetchTickets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const apiStatus = statusFilter !== 'all' ? statusFilter : undefined
      const data = await getTickets(apiStatus)
      setTickets(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tickets')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    fetchTickets()
  }, [fetchTickets])

  const filteredTickets = useMemo(() => {
    if (priorityFilter === 'all') return tickets
    return tickets.filter(ticket => ticket.priority === priorityFilter)
  }, [tickets, priorityFilter])

  const handleCreateTicket = async (data: { query: string; category: string; priority: string }) => {
    try {
      const created = await createTicket({
        query: data.query,
        category: data.category,
        priority: data.priority as 'low' | 'medium' | 'high' | 'critical'
      })
      setTickets([created as Ticket, ...tickets])
      setShowForm(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create ticket')
    }
  }

  const handleStatusUpdate = async (ticketId: string, newStatus: string) => {
    try {
      const updated = await updateTicket(ticketId, { 
        status: newStatus as 'open' | 'in_progress' | 'resolved' | 'escalated' | 'closed' 
      })
      setTickets(tickets.map(ticket => 
        ticket.id === ticketId ? { ...ticket, status: updated.status as Ticket['status'] } : ticket
      ))
      if (selectedTicket?.id === ticketId) {
        setSelectedTicket({ ...selectedTicket, status: updated.status as Ticket['status'] })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update ticket')
    }
  }

  const handleSelectTicket = (id: string) => {
    const ticket = tickets.find(t => t.id === id) || null
    setSelectedTicket(ticket)
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Support Tickets</h1>
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : 'New Ticket'}
        </Button>
      </div>

      {error && (
        <Card className="border-red-500 bg-red-50">
          <CardContent className="py-3 text-red-700">{error}</CardContent>
        </Card>
      )}

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
              {loading ? 'Loading...' : `Showing ${filteredTickets.length} of ${tickets.length} tickets`}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-semibold mb-3">Your Tickets</h2>
          {loading ? (
            <Card><CardContent className="py-8 text-center text-muted-foreground">Loading tickets...</CardContent></Card>
          ) : (
            <TicketList 
              tickets={filteredTickets} 
              onSelect={handleSelectTicket} 
            />
          )}
        </div>

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
