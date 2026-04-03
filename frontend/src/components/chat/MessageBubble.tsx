import { format } from 'date-fns'
import { Badge } from '@/components/ui/badge'

interface MessageBubbleProps {
  content: string
  sender: 'user' | 'bot' | 'hr_agent' | 'system'
  timestamp: string
  intent?: string
  sentiment?: string
}

export function MessageBubble({ content, sender, timestamp, intent, sentiment }: MessageBubbleProps) {
  const isUser = sender === 'user'
  const isBot = sender === 'bot'
  
  // Debug mode - set to true to see intent/sentiment labels
  const showDebug = false;
  
  const getSentimentVariant = (sentiment?: string) => {
    switch (sentiment) {
      case 'positive': return 'default'
      case 'negative': return 'destructive'
      case 'neutral': return 'secondary'
      default: return 'secondary'
    }
  }
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[70%] rounded-lg px-4 py-2 ${
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted'
        }`}
      >
        {isBot && showDebug && (intent || sentiment) && (
          <div className="flex gap-1 mb-2 flex-wrap">
            {intent && (
              <Badge variant="outline" className="text-xs">
                {intent}
              </Badge>
            )}
            {sentiment && (
              <Badge variant={getSentimentVariant(sentiment)} className="text-xs">
                {sentiment}
              </Badge>
            )}
          </div>
        )}
        <p className="text-sm">{content}</p>
        <p className={`text-xs mt-1 ${isUser ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
          {format(new Date(timestamp), 'HH:mm')}
        </p>
      </div>
    </div>
  )
}
