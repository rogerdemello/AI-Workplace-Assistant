import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'

const EMAIL_TYPES = [
  { value: 'leave_request', label: 'Leave Request' },
  { value: 'follow_up', label: 'Follow Up' },
  { value: 'complaint', label: 'Complaint' },
  { value: 'resignation', label: 'Resignation' },
  { value: 'general', label: 'General' }
]

const TONES = [
  { value: 'formal', label: 'Formal', description: 'Professional and formal' },
  { value: 'neutral', label: 'Neutral', description: 'Clear and neutral' },
  { value: 'friendly', label: 'Friendly', description: 'Casual and friendly' }
]

export function EmailDraftPage() {
  const [emailType, setEmailType] = useState('')
  const [tone, setTone] = useState('')
  const [context, setContext] = useState('')
  const [draft, setDraft] = useState<{ subject: string; body: string } | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    if (!emailType || !tone) return
    setIsLoading(true)
    
    // Simulated response
    setTimeout(() => {
      setDraft({
        subject: tone === 'formal' ? 'Leave Request - John Doe' : 'Taking some time off',
        body: tone === 'formal' 
          ? 'Dear Manager,\n\nI would like to request leave from [dates] due to [reason].\n\nThank you,\nJohn Doe'
          : tone === 'neutral'
          ? 'Hi,\n\nI need to take leave from [dates]. Please approve.\n\nThanks,\nJohn'
          : 'Hey!\n\nJust wanted to let you know I need some time off [dates]. Thanks!\n\nCheers,\nJohn'
      })
      setIsLoading(false)
    }, 1000)
  }

  const handleCopy = () => {
    if (draft) {
      navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="container mx-auto py-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">Email Draft Assistant</h1>
      
      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Compose Email</CardTitle>
            <CardDescription>Select the type and tone to generate a professional email</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email-type">Email Type</Label>
              <Select value={emailType} onValueChange={setEmailType}>
                <SelectTrigger id="email-type"><SelectValue placeholder="Select email type" /></SelectTrigger>
                <SelectContent>
                  {EMAIL_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <Label>Tone</Label>
              <div className="flex gap-2 mt-2">
                {TONES.map(t => (
                  <Button 
                    key={t.value} 
                    variant={tone === t.value ? 'default' : 'outline'}
                    onClick={() => setTone(t.value)}
                    className="flex-1"
                  >
                    {t.label}
                  </Button>
                ))}
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="context">Additional Context (optional)</Label>
              <Textarea id="context" value={context} onChange={(e) => setContext(e.target.value)} placeholder="Any specific details..." />
            </div>
            
            <Button onClick={handleGenerate} disabled={!emailType || !tone || isLoading} className="w-full">
              {isLoading ? 'Generating...' : 'Generate Draft'}
            </Button>
          </CardContent>
        </Card>
        
        {draft && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Generated Draft</CardTitle>
                <Badge className="mt-1">{tone}</Badge>
              </div>
              <Button variant="outline" onClick={handleCopy}>{copied ? 'Copied!' : 'Copy'}</Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="subject">Subject</Label>
                <Textarea id="subject" value={draft.subject} onChange={(e) => setDraft({...draft, subject: e.target.value})} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="body">Body</Label>
                <Textarea id="body" value={draft.body} onChange={(e) => setDraft({...draft, body: e.target.value})} rows={8} />
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
