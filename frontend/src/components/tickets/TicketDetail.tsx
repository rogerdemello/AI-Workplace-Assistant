import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface Ticket {
  id: string
  query: string
  category: string
  status: string
  priority: string
  created_at: string
}

interface TicketDetailProps {
  ticket: Ticket
  onClose: () => void
  onStatusUpdate?: (ticketId: string, newStatus: string) => void
}

const statusOptions = [
  { value: 'open', label: 'Open', color: 'bg-blue-100 text-blue-800' },
  { value: 'in_progress', label: 'In Progress', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'escalated', label: 'Escalated', color: 'bg-orange-100 text-orange-800' },
  { value: 'resolved', label: 'Resolved', color: 'bg-green-100 text-green-800' },
  { value: 'closed', label: 'Closed', color: 'bg-gray-100 text-gray-800' }
]

export function TicketDetail({ ticket, onClose, onStatusUpdate }: TicketDetailProps) {
  const [currentStatus, setCurrentStatus] = useState(ticket.status)
  const [isUpdating, setIsUpdating] = useState(false)

  const handleStatusChange = (newStatus: string) => {
    setIsUpdating(true)
    setCurrentStatus(newStatus)
    
    if (onStatusUpdate) {
      onStatusUpdate(ticket.id, newStatus)
    }
    
    setTimeout(() => setIsUpdating(false), 500)
  }

  const currentStatusInfo = statusOptions.find(s => s.value === currentStatus) || statusOptions[0]

  return (
    <Card className="h-fit">
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
            <p className="capitalize">{ticket.priority}</p>
          </div>
        </div>

        {/* Status Update */}
        <div className="space-y-2">
          <Label className="text-muted-foreground">Status</Label>
          <div className="flex items-center gap-3">
            <Badge className={currentStatusInfo.color}>
              {currentStatusInfo.label}
            </Badge>
            <Select value={currentStatus} onValueChange={handleStatusChange}>
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
          <p className="text-sm">{new Date(ticket.created_at).toLocaleString()}</p>
        </div>

        {/* Ticket ID */}
        <div className="space-y-2">
          <Label className="text-muted-foreground">Ticket ID</Label>
          <p className="text-sm font-mono text-muted-foreground">{ticket.id}</p>
        </div>
      </CardContent>
    </Card>
  )
}
