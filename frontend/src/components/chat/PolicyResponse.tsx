import { Card, CardContent } from '@/components/ui/card'

interface Citation {
  id: string
  title?: string
  content?: string
}

interface PolicyResponseProps {
  answer: string
  citations?: Citation[]
}

export function PolicyResponse({ answer, citations = [] }: PolicyResponseProps) {
  const citationIds: string[] = []
  const answerWithMarkers = answer.replace(/\[(\d+)\]/g, (_, id) => {
    citationIds.push(id)
    return ''
  }).trim()

  return (
    <Card className="mt-4 bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
            <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-blue-800 flex items-center gap-2">
              Policy Information
            </h4>
            
            <div className="mt-3 text-sm text-blue-900 whitespace-pre-wrap">
              {answerWithMarkers}
            </div>
            
            {citations.length > 0 && (
              <div className="mt-4 space-y-2">
                <h5 className="text-xs font-semibold text-blue-700 uppercase tracking-wide flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                  Sources
                </h5>
                <div className="space-y-2">
                  {citations.map((citation, index) => (
                    <div 
                      key={citation.id || index}
                      className="text-xs bg-blue-100/50 rounded-md p-2 border border-blue-200"
                    >
                      {citation.title && (
                        <p className="font-medium text-blue-800">{citation.title}</p>
                      )}
                      {citation.content && (
                        <p className="text-blue-700 mt-1 line-clamp-2">
                          {citation.content}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {citationIds.length > 0 && citations.length === 0 && (
              <div className="mt-3 text-xs text-blue-600">
                Referenced: [{citationIds.join(', ')}]
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
