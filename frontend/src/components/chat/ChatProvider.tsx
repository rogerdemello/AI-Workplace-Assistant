'use client'

import { createContext, useContext, useState, ReactNode } from 'react'

interface Message {
  id: string
  role: 'user' | 'bot'
  content: string
  timestamp: Date
}

interface ChatContextType {
  isOpen: boolean
  setIsOpen: (open: boolean) => void
  messages: Message[]
  addMessage: (content: string, role: 'user' | 'bot') => void
  isTyping: boolean
  setIsTyping: (typing: boolean) => void
}

const ChatContext = createContext<ChatContextType | undefined>(undefined)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'bot',
      content: 'Hi! I\'m Amber, your HR assistant. How can I help you today?',
      timestamp: new Date(),
    },
  ])
  const [isTyping, setIsTyping] = useState(false)

  const addMessage = (content: string, role: 'user' | 'bot') => {
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        role,
        content,
        timestamp: new Date(),
      },
    ])
  }

  return (
    <ChatContext.Provider
      value={{
        isOpen,
        setIsOpen,
        messages,
        addMessage,
        isTyping,
        setIsTyping,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const context = useContext(ChatContext)
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider')
  }
  return context
}
