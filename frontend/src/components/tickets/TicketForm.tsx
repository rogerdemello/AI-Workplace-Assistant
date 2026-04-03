import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface TicketFormProps {
  onSubmit: (data: { query: string; category: string; priority: string }) => void
  onCancel: () => void
}

const categories = [
  { value: 'leave', label: 'Leave' },
  { value: 'benefits', label: 'Benefits' },
  { value: 'payroll', label: 'Payroll' },
  { value: 'general', label: 'General' }
]

const priorities = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' }
]

export function TicketForm({ onSubmit, onCancel }: TicketFormProps) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [priority, setPriority] = useState('medium')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || !category) return
    
    onSubmit({ query: query.trim(), category, priority })
    
    // Reset form
    setQuery('')
    setCategory('')
    setPriority('medium')
  }

  const isValid = query.trim().length > 0 && category.length > 0

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Query */}
      <div className="space-y-2">
        <Label htmlFor="query">Describe your issue</Label>
        <Textarea 
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Describe your issue or question..."
          rows={4}
          required
        />
      </div>

      {/* Category */}
      <div className="space-y-2">
        <Label htmlFor="category">Category</Label>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger id="category">
            <SelectValue placeholder="Select a category" />
          </SelectTrigger>
          <SelectContent>
            {categories.map((cat) => (
              <SelectItem key={cat.value} value={cat.value}>
                {cat.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Priority */}
      <div className="space-y-2">
        <Label htmlFor="priority">Priority</Label>
        <Select value={priority} onValueChange={setPriority}>
          <SelectTrigger id="priority">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {priorities.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <Button type="submit" disabled={!isValid}>
          Submit Ticket
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
