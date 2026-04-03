import { useState } from 'react'
import { SearchBox } from '@/components/search/SearchBox'
import { SearchResult } from '@/components/search/SearchResult'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface SearchResultItem {
  id: string
  content: string
  source: string
  score: number
  highlightedContent?: string
}

export function SearchPage() {
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  
  const handleSearch = async (_query: string) => {
    setIsLoading(true)
    setHasSearched(true)
    
    try {
      // TODO: Call API with query: _query
      // const response = await fetch('/api/v1/rag/search', ...)
      
      // Simulated results
      setResults([
        {
          id: '1',
          content: 'Employees are entitled to 20 days of paid vacation per year...',
          source: 'Leave Policy (Section 3.1)',
          score: 0.92,
          highlightedContent: 'Employees are entitled to <mark>20 days</mark> of paid vacation per year...'
        },
        {
          id: '2',
          content: 'Vacation requests should be submitted at least 2 weeks in advance...',
          source: 'Leave Policy (Section 3.2)',
          score: 0.85,
          highlightedContent: 'Vacation requests should be submitted at least <mark>2 weeks</mark> in advance...'
        },
        {
          id: '3',
          content: 'Holiday calendar for 2026 is available on the company intranet...',
          source: 'Holiday Policy',
          score: 0.78,
          highlightedContent: 'Holiday calendar for <mark>2026</mark> is available on the company intranet...'
        }
      ])
    } catch (error) {
      console.error('Search error:', error)
    } finally {
      setIsLoading(false)
    }
  }
  
  return (
    <div className="container mx-auto py-8">
      <Card>
        <CardHeader>
          <CardTitle>Knowledge Base Search</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SearchBox onSearch={handleSearch} isLoading={isLoading} />
          
          {isLoading && (
            <div className="text-center py-8 text-muted-foreground">
              Searching knowledge base...
            </div>
          )}
          
          {!isLoading && hasSearched && results.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              No results found. Try a different search term.
            </div>
          )}
          
          {!isLoading && results.map((result) => (
            <SearchResult
              key={result.id}
              content={result.content}
              source={result.source}
              score={result.score}
              highlightedContent={result.highlightedContent}
            />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
