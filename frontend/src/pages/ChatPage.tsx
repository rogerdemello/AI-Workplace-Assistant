import { useState, useEffect, useRef } from 'react'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Message {
  id: string
  content: string
  sender: 'user' | 'bot' | 'hr_agent' | 'system'
  timestamp: string
  intent?: string
  sentiment?: string
}

// Simple auth token storage (in production, use proper auth context)
const getAuthHeaders = async (): Promise<HeadersInit> => {
  let token = localStorage.getItem('auth_token')
  
  if (!token) {
    try {
      const loginRes = await fetch(`${API_BASE_URL}/api/v1/demo/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: "Demo User", email: "demo@example.com" })
      })
      if (loginRes.ok) {
        const loginData = await loginRes.json()
        token = loginData.access_token as string
        localStorage.setItem('auth_token', token)
      }
    } catch (e) {
      console.error('Demo login failed:', e)
    }
  }
  
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  }
}

// Clear auth and force re-login
const clearAuth = () => {
  localStorage.removeItem('auth_token')
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const isNewConversation = useRef(true)
  
  // Load conversation history on mount
  useEffect(() => {
    // TODO: Fetch from API (future: load existing conversation)
  }, [])
  
  const handleSendMessage = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      sender: 'user',
      timestamp: new Date().toISOString()
    }
    
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    
    try {
      let currentConversationId = conversationId
      
      if (isNewConversation.current || !currentConversationId) {
        const startResponse = await fetch(`${API_BASE_URL}/api/v1/chat/conversations/start`, {
          method: 'POST',
          headers: await getAuthHeaders(),
          body: JSON.stringify({ message: content }),
        })
        
        if (startResponse.status === 401) {
          // Clear bad token and retry login
          clearAuth()
          const loginRes = await fetch(`${API_BASE_URL}/api/v1/demo/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: "Demo User", email: "demo@example.com" })
          })
          if (loginRes.ok) {
            const loginData = await loginRes.json()
            localStorage.setItem('auth_token', loginData.access_token)
            // Retry with new token
            const retryResponse = await fetch(`${API_BASE_URL}/api/v1/chat/conversations/start`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${loginData.access_token}` },
              body: JSON.stringify({ message: content }),
            })
            if (retryResponse.ok) {
              const startData = await retryResponse.json()
              currentConversationId = startData.conversation_id
              setConversationId(currentConversationId)
              isNewConversation.current = false
              
              if (startData.greeting) {
                const greetingMessage: Message = {
                  id: (Date.now() + 1).toString(),
                  content: startData.greeting,
                  sender: 'bot',
                  timestamp: new Date().toISOString()
                }
                setMessages(prev => [...prev, greetingMessage])
              }
              setIsLoading(false)
              return
            }
          }
          // If still failing, show error
          const errorMessage: Message = {
            id: (Date.now() + 1).toString(),
            content: 'Please log in to use the chat. (Auth required for this demo)',
            sender: 'system',
            timestamp: new Date().toISOString()
          }
          setMessages(prev => [...prev, errorMessage])
          setIsLoading(false)
          return
        }
        
        if (!startResponse.ok) {
          throw new Error('Failed to start conversation')
        }
        
        const startData = await startResponse.json()
        currentConversationId = startData.conversation_id
        setConversationId(currentConversationId)
        isNewConversation.current = false
        
        if (startData.greeting) {
          const greetingMessage: Message = {
            id: (Date.now() + 1).toString(),
            content: startData.greeting,
            sender: 'bot',
            timestamp: new Date().toISOString()
          }
          setMessages(prev => [...prev, greetingMessage])
        }
      }
      
      const response = await fetch(`${API_BASE_URL}/api/v1/chat/conversations/${currentConversationId}/respond`, {
        method: 'POST',
        headers: await getAuthHeaders(),
        body: JSON.stringify({ message: content }),
      })
      
      if (response.status === 401) {
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          content: 'Please log in to continue chatting.',
          sender: 'system',
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, errorMessage])
        setIsLoading(false)
        return
      }
      
      if (!response.ok) {
        throw new Error('Failed to send message')
      }
      
      const data = await response.json()
      
      const botMessage: Message = {
        id: (Date.now() + 2).toString(),
        content: data.response,
        sender: 'bot',
        timestamp: new Date().toISOString(),
        intent: data.intent,
        sentiment: data.sentiment
      }
      setMessages(prev => [...prev, botMessage])
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: 'Sorry, I encountered an error. Please try again.',
        sender: 'system',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }
  
  return (
    <div className="container mx-auto py-8">
      <Card>
        <CardHeader>
          <CardTitle>HR Assistant Chat</CardTitle>
        </CardHeader>
        <CardContent>
          <ChatWindow
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>
    </div>
  )
}
