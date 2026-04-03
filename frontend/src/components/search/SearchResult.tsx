import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface SearchResultProps {
  content: string
  source: string
  score: number
  highlightedContent?: string
}

export function SearchResult({ content, source, score, highlightedContent }: SearchResultProps) {
  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-sm font-medium">{source}</CardTitle>
          <Badge variant="outline">
            {Math.round(score * 100)}% match
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {highlightedContent ? (
          <p 
            className="text-sm text-muted-foreground"
            dangerouslySetInnerHTML={{ __html: highlightedContent }}
          />
        ) : (
          <p className="text-sm text-muted-foreground">{content}</p>
        )}
      </CardContent>
    </Card>
  )
}
