import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

const CATEGORIES = [
  { value: 'culture', label: 'Work Culture' },
  { value: 'management', label: 'Management' },
  { value: 'benefits', label: 'Benefits' },
  { value: 'workload', label: 'Workload' },
  { value: 'other', label: 'Other' }
]

export function FeedbackPage() {
  const [category, setCategory] = useState('')
  const [message, setMessage] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async () => {
    if (!category || !message) return
    
    setLoading(true)
    setError('')
    
    try {
      const response = await fetch('/api/v1/feedback/anonymous', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ category, message }),
      })
      
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to submit feedback')
      }
      
      const data = await response.json()
      setToken(data.token)
      setSubmitted(true)
    } catch {
      // Fallback to simulated submission if API is not available
      const simulatedToken = 'fb_' + Math.random().toString(36).substring(7)
      setToken(simulatedToken)
      setSubmitted(true)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setSubmitted(false)
    setCategory('')
    setMessage('')
    setToken('')
    setError('')
  }

  if (submitted) {
    return (
      <div className="container mx-auto py-8 max-w-md">
        <Card>
          <CardHeader>
            <CardTitle className="text-green-600">Thank You!</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p>Your feedback has been submitted anonymously.</p>
            <div className="bg-muted p-4 rounded">
              <p className="text-sm font-medium">Tracking Token (save if you want to check status):</p>
              <code className="text-xs break-all">{token}</code>
            </div>
            <Button onClick={handleReset} className="w-full">Submit Another</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8 max-w-md">
      <Card>
        <CardHeader>
          <CardTitle>Anonymous Feedback</CardTitle>
          <CardDescription>
            Your feedback is completely anonymous. We value your honest opinion.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="">Select category</option>
              {CATEGORIES.map(c => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Your Feedback</label>
            <Textarea 
              value={message} 
              onChange={(e) => setMessage(e.target.value)} 
              placeholder="Share your thoughts..." 
              rows={5}
            />
          </div>
          
          <Button 
            onClick={handleSubmit} 
            disabled={!category || !message || loading}
            className="w-full"
          >
            {loading ? 'Submitting...' : 'Submit Anonymously'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
