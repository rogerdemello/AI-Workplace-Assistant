'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { TicketList } from '@/components/tickets/TicketList'
import { TicketDetail } from '@/components/tickets/TicketDetail'
import { TicketForm } from '@/components/tickets/TicketForm'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { getTickets, createTicket, updateTicket, listTicketMessages, addTicketMessage, type TicketMessageResponse } from '@/lib/api'

interface Ticket {
  id: string
  query: string
  category: string
  status: 'open' | 'in_progress' | 'resolved' | 'escalated' | 'closed'
  priority: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
  sla_due_at?: string
  sla_warning?: boolean
}

type StatusFilter = 'all' | 'open' | 'in_progress' | 'resolved' | 'escalated' | 'closed'
type PriorityFilter = 'all' | 'low' | 'medium' | 'high' | 'critical'

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [messages, setMessages] = useState<TicketMessageResponse[]>([])
  const [msgLoading, setMsgLoading] = useState(false)
  const [msgSaving, setMsgSaving] = useState(false)
  const [messageText, setMessageText] = useState('')
  
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all')

  const fetchTickets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const apiStatus = statusFilter !== 'all' ? statusFilter : undefined
      const data = await getTickets(apiStatus) as Ticket[]
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

  useEffect(() => {
    if (!selectedTicket) return
    const next = tickets.find(t => t.id === selectedTicket.id) || null
    if (!next) {
      setSelectedTicket(null)
      setMessages([])
      return
    }
    if (next !== selectedTicket) {
      setSelectedTicket(next)
    }
  }, [tickets, selectedTicket])

  const handleCreateTicket = async (data: { query: string; category: string; priority: string }) => {
    try {
      const created = await createTicket({
        query: data.query,
        category: data.category,
        priority: data.priority as 'low' | 'medium' | 'high' | 'critical'
      })
      setTickets((prev) => [created as Ticket, ...prev])
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
      setTickets((prev) => prev.map(ticket => 
        ticket.id === ticketId ? { ...ticket, status: updated.status as Ticket['status'] } : ticket
      ))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update ticket')
    }
  }

  const handleSelectTicket = async (id: string) => {
    const ticket = tickets.find(t => t.id === id) || null
    setSelectedTicket(ticket)
    setMessageText('')

    if (!ticket) {
      setMessages([])
      return
    }

    setMsgLoading(true)
    try {
      const thread = await listTicketMessages(id)
      setMessages(thread)
    } catch {
      setMessages([])
    } finally {
      setMsgLoading(false)
    }
  }

  const handlePostMessage = async () => {
    if (!selectedTicket || !messageText.trim()) return

    setMsgSaving(true)
    setError(null)
    try {
      await addTicketMessage(selectedTicket.id, messageText.trim())
      setMessageText('')
      const thread = await listTicketMessages(selectedTicket.id)
      setMessages(thread)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to post comment')
    } finally {
      setMsgSaving(false)
    }
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
                  <SelectItem value="escalated">Escalated</SelectItem>
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
            <div className="space-y-4">
              <TicketDetail 
                ticket={selectedTicket} 
                onClose={() => {
                  setSelectedTicket(null)
                  setMessages([])
                  setMessageText('')
                }}
                onStatusUpdate={handleStatusUpdate}
              />

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Ticket Conversation</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {msgLoading ? (
                    <p className="text-sm text-muted-foreground">Loading messages...</p>
                  ) : messages.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No updates yet. Add a note for HR.</p>
                  ) : (
                    <div className="max-h-64 space-y-2 overflow-y-auto rounded-md border p-3">
                      {messages.map((msg) => (
                        <div key={msg.id} className="rounded-md bg-muted/50 px-3 py-2">
                          <p className="text-sm">{msg.message_text}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{new Date(msg.created_at).toLocaleString()}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label htmlFor="ticket-comment">Add comment</Label>
                    <Textarea
                      id="ticket-comment"
                      value={messageText}
                      onChange={(e) => setMessageText(e.target.value)}
                      placeholder="Share additional details with HR..."
                      rows={3}
                    />
                    <Button onClick={handlePostMessage} disabled={msgSaving || !messageText.trim()}>
                      {msgSaving ? 'Posting...' : 'Post comment'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
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
