import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

interface Ticket {
  id: string
  query: string
  category: string
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  priority: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
}

interface TicketListProps {
  tickets: Ticket[]
  onSelect: (id: string) => void
}

const statusColors: Record<string, string> = {
  open: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-yellow-100 text-yellow-800',
  resolved: 'bg-green-100 text-green-800',
  closed: 'bg-gray-100 text-gray-800'
}

const priorityColors: Record<string, string> = {
  low: 'text-green-600',
  medium: 'text-yellow-600',
  high: 'text-orange-600',
  critical: 'text-red-600'
}

export function TicketList({ tickets, onSelect }: TicketListProps) {
  if (tickets.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No tickets found. Create a new ticket to get started.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {tickets.map((ticket) => (
        <Card 
          key={ticket.id} 
          className="cursor-pointer hover:bg-muted/50 transition-colors" 
          onClick={() => onSelect(ticket.id)}
        >
          <CardContent className="p-4">
            <div className="flex justify-between items-start gap-4">
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{ticket.query}</p>
                <p className="text-sm text-muted-foreground mt-1">{ticket.category}</p>
              </div>
              <div className="flex flex-col gap-2 items-end">
                <Badge className={statusColors[ticket.status]}>{ticket.status.replace('_', ' ')}</Badge>
                <span className={`text-xs font-medium ${priorityColors[ticket.priority]}`}>
                  {ticket.priority}
                </span>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              {new Date(ticket.created_at).toLocaleDateString()}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
