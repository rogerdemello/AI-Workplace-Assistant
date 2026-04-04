'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'

interface SurveyQuestion {
  id: string
  type: 'text' | 'rating' | 'choice' | 'multiple_choice'
  question: string
  options?: string[]
  required: boolean
}

interface Survey {
  id: string
  title: string
  description?: string
  questions: SurveyQuestion[]
  is_active: boolean
  allow_anonymous: boolean
  created_at: string
}

const sampleSurveys: Survey[] = [
  {
    id: '1',
    title: 'Employee Satisfaction Survey',
    description: 'Help us understand your workplace experience',
    is_active: true,
    allow_anonymous: true,
    created_at: '2026-03-20T10:00:00Z',
    questions: [
      { id: 'q1', type: 'rating', question: 'How satisfied are you with your current role?', required: true },
      { id: 'q2', type: 'choice', question: 'How would you rate work-life balance?', options: ['Excellent', 'Good', 'Fair', 'Poor'], required: true },
      { id: 'q3', type: 'text', question: 'What improvements would you suggest?', required: false }
    ]
  },
  {
    id: '2',
    title: 'Team Collaboration Feedback',
    description: 'Share your thoughts on team communication',
    is_active: true,
    allow_anonymous: false,
    created_at: '2026-03-15T14:30:00Z',
    questions: [
      { id: 'q1', type: 'rating', question: 'How effective is team communication?', required: true },
      { id: 'q2', type: 'multiple_choice', question: 'Which tools do you use most?', options: ['Slack', 'Email', 'Microsoft Teams', 'Zoom', 'In-person meetings'], required: true }
    ]
  },
  {
    id: '3',
    title: 'Remote Work Policy Survey',
    description: 'Your input on remote work arrangements',
    is_active: false,
    allow_anonymous: true,
    created_at: '2026-02-10T09:00:00Z',
    questions: [
      { id: 'q1', type: 'choice', question: 'Preferred work arrangement?', options: ['Fully remote', 'Hybrid', 'Fully office'], required: true }
    ]
  }
]

type View = 'list' | 'take' | 'create' | 'thankyou'

export default function SurveysPage() {
  const [surveys] = useState<Survey[]>(sampleSurveys)
  const [selectedSurvey, setSelectedSurvey] = useState<Survey | null>(null)
  const [currentView, setCurrentView] = useState<View>('list')
  const [responses, setResponses] = useState<Record<string, any>>({})
  const [anonymous, setAnonymous] = useState(false)
  
  const [newSurvey, setNewSurvey] = useState({
    title: '',
    description: '',
    allowAnonymous: false,
    questions: [] as SurveyQuestion[]
  })
  const [newQuestion, setNewQuestion] = useState<SurveyQuestion>({
    id: '',
    type: 'text',
    question: '',
    required: true
  })

  const activeSurveys = surveys.filter(s => s.is_active)

  const handleStartSurvey = (survey: Survey) => {
    setSelectedSurvey(survey)
    setResponses({})
    setAnonymous(survey.allow_anonymous)
    setCurrentView('take')
  }

  const handleResponseChange = (questionId: string, value: any) => {
    setResponses(prev => ({ ...prev, [questionId]: value }))
  }

  const handleSubmitSurvey = () => {
    console.log('Submitting survey:', { surveyId: selectedSurvey?.id, responses, anonymous })
    setCurrentView('thankyou')
  }

  const handleBackToList = () => {
    setSelectedSurvey(null)
    setResponses({})
    setCurrentView('list')
  }

  const handleAddQuestion = () => {
    if (newQuestion.question.trim()) {
      setNewSurvey(prev => ({
        ...prev,
        questions: [...prev.questions, { ...newQuestion, id: `q${prev.questions.length + 1}` }]
      }))
      setNewQuestion({ id: '', type: 'text', question: '', required: true })
    }
  }

  const handleCreateSurvey = () => {
    console.log('Creating survey:', newSurvey)
    setNewSurvey({ title: '', description: '', allowAnonymous: false, questions: [] })
    setCurrentView('list')
  }

  const renderQuestion = (question: SurveyQuestion) => {
    const value = responses[question.id]
    switch (question.type) {
      case 'text':
        return <Textarea value={value || ''} onChange={(e) => handleResponseChange(question.id, e.target.value)} placeholder="Enter your response..." className="min-h-[100px]" />
      case 'rating':
        return (
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((num) => (
              <Button key={num} variant={value === num ? 'default' : 'outline'} size="sm" onClick={() => handleResponseChange(question.id, num)}>{num}</Button>
            ))}
          </div>
        )
      case 'choice':
        return (
          <div className="space-y-2">
            {question.options?.map((option) => (
              <div key={option} className="flex items-center gap-2">
                <input type="radio" id={`${question.id}-${option}`} name={question.id} checked={value === option} onChange={() => handleResponseChange(question.id, option)} className="w-4 h-4" />
                <Label htmlFor={`${question.id}-${option}`}>{option}</Label>
              </div>
            ))}
          </div>
        )
      case 'multiple_choice':
        return (
          <div className="space-y-2">
            {question.options?.map((option) => (
              <div key={option} className="flex items-center gap-2">
                <input type="checkbox" id={`${question.id}-${option}`} checked={(value || []).includes(option)} onChange={(e) => {
                  const current = value || []
                  if (e.target.checked) handleResponseChange(question.id, [...current, option])
                  else handleResponseChange(question.id, current.filter((v: string) => v !== option))
                }} className="w-4 h-4" />
                <Label htmlFor={`${question.id}-${option}`}>{option}</Label>
              </div>
            ))}
          </div>
        )
      default:
        return null
    }
  }

  if (currentView === 'thankyou') {
    return (
      <div className="container mx-auto py-8">
        <Card className="max-w-md mx-auto">
          <CardHeader><CardTitle className="text-center text-green-600">Thank You!</CardTitle></CardHeader>
          <CardContent className="text-center space-y-4">
            <p>Your response has been submitted successfully.</p>
            <p className="text-sm text-muted-foreground">{anonymous ? 'Your response was submitted anonymously.' : 'Thank you for your feedback!'}</p>
            <Button onClick={handleBackToList}>Back to Surveys</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (currentView === 'take' && selectedSurvey) {
    const requiredAnswered = selectedSurvey.questions.filter(q => q.required).every(q => responses[q.id])
    return (
      <div className="container mx-auto py-8 max-w-2xl">
        <Button variant="ghost" onClick={handleBackToList} className="mb-4">← Back to Surveys</Button>
        <Card>
          <CardHeader>
            <CardTitle>{selectedSurvey.title}</CardTitle>
            {selectedSurvey.description && <CardDescription>{selectedSurvey.description}</CardDescription>}
            {selectedSurvey.allow_anonymous && <Badge variant="secondary" className="mt-2">Anonymous Response Allowed</Badge>}
          </CardHeader>
          <CardContent className="space-y-6">
            {selectedSurvey.questions.map((question, index) => (
              <div key={question.id} className="space-y-3">
                <Label className="text-base font-medium">{index + 1}. {question.question}{question.required && <span className="text-red-500 ml-1">*</span>}</Label>
                {renderQuestion(question)}
              </div>
            ))}
            {selectedSurvey.allow_anonymous && (
              <div className="flex items-center gap-2 pt-4 border-t">
                <input type="checkbox" id="anonymous" checked={anonymous} onChange={(e) => setAnonymous(e.target.checked)} className="w-4 h-4" />
                <Label htmlFor="anonymous">Submit anonymously</Label>
              </div>
            )}
            <Button onClick={handleSubmitSurvey} disabled={!requiredAnswered} className="w-full">Submit Response</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (currentView === 'create') {
    return (
      <div className="container mx-auto py-8 max-w-2xl">
        <Button variant="ghost" onClick={() => setCurrentView('list')} className="mb-4">← Back to Surveys</Button>
        <Card>
          <CardHeader><CardTitle>Create New Survey</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Survey Title</Label>
              <Input id="title" value={newSurvey.title} onChange={(e) => setNewSurvey(prev => ({ ...prev, title: e.target.value }))} placeholder="Enter survey title" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" value={newSurvey.description} onChange={(e) => setNewSurvey(prev => ({ ...prev, description: e.target.value }))} placeholder="Describe the survey purpose" />
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="allowAnonymous" checked={newSurvey.allowAnonymous} onChange={(e) => setNewSurvey(prev => ({ ...prev, allowAnonymous: e.target.checked }))} className="w-4 h-4" />
              <Label htmlFor="allowAnonymous">Allow anonymous responses</Label>
            </div>
            <div className="border-t pt-4 space-y-4">
              <h3 className="font-semibold">Add Questions</h3>
              <div className="space-y-2">
                <Label>Question</Label>
                <Textarea value={newQuestion.question} onChange={(e) => setNewQuestion(prev => ({ ...prev, question: e.target.value }))} placeholder="Enter your question" />
              </div>
              <div className="flex gap-4">
                <div className="space-y-2">
                  <Label>Type</Label>
                  <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={newQuestion.type} onChange={(e) => setNewQuestion(prev => ({ ...prev, type: e.target.value as SurveyQuestion['type'] }))}>
                    <option value="text">Text</option>
                    <option value="rating">Rating (1-5)</option>
                    <option value="choice">Single Choice</option>
                    <option value="multiple_choice">Multiple Choice</option>
                  </select>
                </div>
                {(newQuestion.type === 'choice' || newQuestion.type === 'multiple_choice') && (
                  <div className="space-y-2 flex-1">
                    <Label>Options (comma separated)</Label>
                    <Input placeholder="Option 1, Option 2, Option 3" onChange={(e) => setNewQuestion(prev => ({ ...prev, options: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }))} />
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="required" checked={newQuestion.required} onChange={(e) => setNewQuestion(prev => ({ ...prev, required: e.target.checked }))} className="w-4 h-4" />
                <Label htmlFor="required">Required</Label>
              </div>
              <Button type="button" variant="outline" onClick={handleAddQuestion}>Add Question</Button>
              {newSurvey.questions.length > 0 && (
                <div className="space-y-2 mt-4">
                  <Label>Questions added:</Label>
                  {newSurvey.questions.map((q, idx) => (
                    <div key={idx} className="flex justify-between items-center p-2 bg-muted rounded">
                      <span className="text-sm">{idx + 1}. {q.question}</span>
                      <Badge variant="outline">{q.type}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <Button onClick={handleCreateSurvey} disabled={!newSurvey.title || newSurvey.questions.length === 0} className="w-full">Create Survey</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Surveys</h1>
        <Button onClick={() => setCurrentView('create')}>Create Survey</Button>
      </div>
      <div className="grid gap-4">
        {activeSurveys.map((survey) => (
          <Card key={survey.id} className="cursor-pointer hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle className="text-lg">{survey.title}</CardTitle>
                {survey.description && <CardDescription className="mt-1">{survey.description}</CardDescription>}
              </div>
              <div className="flex gap-2">
                {survey.allow_anonymous && <Badge variant="secondary">Anonymous</Badge>}
                <Badge variant={survey.is_active ? 'default' : 'outline'}>{survey.is_active ? 'Active' : 'Closed'}</Badge>
              </div>
            </CardHeader>
            <CardContent className="flex justify-between items-center">
              <div className="text-sm text-muted-foreground">{survey.questions.length} question{survey.questions.length !== 1 ? 's' : ''}</div>
              <Button onClick={() => handleStartSurvey(survey)}>Take Survey</Button>
            </CardContent>
          </Card>
        ))}
        {activeSurveys.length === 0 && (
          <Card><CardContent className="py-12 text-center text-muted-foreground">No active surveys at the moment. Check back later!</CardContent></Card>
        )}
      </div>
    </div>
  )
}
