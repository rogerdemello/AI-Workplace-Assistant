import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface Ticket {
  id: string
  query: string
  category: string
  status?: string | null
  priority?: string | null
  created_at?: string | null
  sla_due_at?: string
  sla_warning?: boolean
}

interface TicketDetailProps {
  ticket: Ticket
  onClose: () => void
  onStatusUpdate?: (ticketId: string, newStatus: string) => Promise<void> | void
}

const statusOptions = [
  { value: 'open', label: 'Open', color: 'bg-blue-100 text-blue-800' },
  { value: 'in_progress', label: 'In Progress', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'escalated', label: 'Escalated', color: 'bg-orange-100 text-orange-800' },
  { value: 'resolved', label: 'Resolved', color: 'bg-green-100 text-green-800' },
  { value: 'closed', label: 'Closed', color: 'bg-gray-100 text-gray-800' }
]

export function TicketDetail({ ticket, onClose, onStatusUpdate }: TicketDetailProps) {
  const [currentStatus, setCurrentStatus] = useState(ticket.status || 'open')
  const [isUpdating, setIsUpdating] = useState(false)

  useEffect(() => {
    setCurrentStatus(ticket.status || 'open')
  }, [ticket.id, ticket.status])

  const handleStatusChange = async (newStatus: string) => {
    const previous = currentStatus
    setIsUpdating(true)
    setCurrentStatus(newStatus)
    
    if (onStatusUpdate) {
      try {
        await onStatusUpdate(ticket.id, newStatus)
      } catch {
        setCurrentStatus(previous)
      }
    }
    
    setTimeout(() => setIsUpdating(false), 500)
  }

  const currentStatusInfo = statusOptions.find(s => s.value === currentStatus) || statusOptions[0]

  return (
    <Card className="h-fit" data-testid="ticket-detail">
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg">Ticket Details</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Query */}
        <div className="space-y-2">
          <Label className="text-muted-foreground">Query</Label>
          <p className="font-medium">{ticket.query}</p>
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-muted-foreground">Category</Label>
            <p className="capitalize">{ticket.category}</p>
          </div>
          
          <div className="space-y-2">
            <Label className="text-muted-foreground">Priority</Label>
            <p className="capitalize" data-testid="ticket-priority">{ticket.priority || 'Medium'}</p>
          </div>
        </div>

        {/* Status Update */}
        <div className="space-y-2">
          <Label className="text-muted-foreground">Status</Label>
          <div className="flex items-center gap-3">
            <Badge className={currentStatusInfo.color} data-testid="ticket-status">
              {currentStatusInfo.label}
            </Badge>
            <Select value={currentStatus || 'open'} onValueChange={handleStatusChange}>
              <SelectTrigger className="w-[140px]" disabled={isUpdating}>
                <SelectValue placeholder="Change status" />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Created Date */}
        <div className="space-y-2">
          <Label className="text-muted-foreground">Created</Label>
          <p className="text-sm" data-testid="ticket-created-at">{ticket.created_at ? new Date(ticket.created_at).toLocaleString() : '—'}</p>
        </div>

        {/* SLA */}
        {ticket.sla_due_at ? (
          <div className="space-y-2">
            <Label className="text-muted-foreground">SLA Due</Label>
            <p className={`text-sm ${ticket.sla_warning ? 'text-amber-700 font-medium' : ''}`}>
              {new Date(ticket.sla_due_at).toLocaleString()}
            </p>
          </div>
        ) : null}

        {/* Ticket ID */}
        <div className="space-y-2">
          <Label className="text-muted-foreground">Ticket ID</Label>
          <p className="text-sm font-mono text-muted-foreground">{ticket.id}</p>
        </div>
      </CardContent>
    </Card>
  )
}
