import { Card, CardContent } from '@/components/ui/card'

interface TicketConfirmationProps {
  department?: string
  issue?: string
  anonymous?: boolean
}

export function TicketConfirmation({ 
  department = 'HR', 
  issue = 'your concern', 
  anonymous = false 
}: TicketConfirmationProps) {
  return (
    <Card className="mt-4 bg-gradient-to-br from-green-50 to-emerald-50 border-green-200">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
            <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-green-800 flex items-center gap-2">
              Ticket Submitted Successfully
            </h4>
            <p className="text-sm text-green-700 mt-1">
              Your ticket has been raised to the {department} team.
            </p>
            
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
                </svg>
                <span className="text-green-800">
                  Issue: {issue.length > 50 ? issue.slice(0, 50) + '...' : issue}
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-sm">
                <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
                <span className="text-green-800">
                  Department: {department}
                </span>
              </div>
              
              {anonymous && (
                <div className="flex items-center gap-2 text-sm">
                  <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  <span className="text-green-800">
                    Submitted anonymously
                  </span>
                </div>
              )}
            </div>
            
            <p className="text-xs text-green-600 mt-3">
              The team will review your ticket and get back to you shortly.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
