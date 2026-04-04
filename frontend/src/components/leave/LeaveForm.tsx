import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface LeaveFormProps {
  onSubmit: (data: {
    start_date: string
    end_date: string
    leave_type: string
    reason: string
  }) => void
  onCancel: () => void
}

const leaveTypes = [
  { value: 'annual', label: 'Annual Leave' },
  { value: 'sick', label: 'Sick Leave' },
  { value: 'personal', label: 'Personal Leave' },
  { value: 'parental', label: 'Parental Leave' },
  { value: 'unpaid', label: 'Unpaid Leave' }
]

export function LeaveForm({ onSubmit, onCancel }: LeaveFormProps) {
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [leaveType, setLeaveType] = useState('')
  const [reason, setReason] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!startDate || !endDate || !leaveType) return

    onSubmit({
      start_date: startDate,
      end_date: endDate,
      leave_type: leaveType,
      reason: reason.trim()
    })

    setStartDate('')
    setEndDate('')
    setLeaveType('')
    setReason('')
  }

  const isValid = startDate && endDate && leaveType && new Date(startDate) <= new Date(endDate)

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4 border rounded-lg bg-muted/30">
      <div className="space-y-2">
        <Label htmlFor="start-date">Start Date</Label>
        <Input
          id="start-date"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="end-date">End Date</Label>
        <Input
          id="end-date"
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          min={startDate}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="leave-type">Leave Type</Label>
        <Select value={leaveType} onValueChange={setLeaveType}>
          <SelectTrigger id="leave-type">
            <SelectValue placeholder="Select leave type" />
          </SelectTrigger>
          <SelectContent>
            {leaveTypes.map((type) => (
              <SelectItem key={type.value} value={type.value}>
                {type.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="reason">Reason (optional)</Label>
        <Textarea
          id="reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Brief reason for leave..."
          rows={2}
        />
      </div>

      <div className="flex gap-2 pt-2">
        <Button type="submit" disabled={!isValid}>
          Submit Request
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}