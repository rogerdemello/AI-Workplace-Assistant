'use client'

import { ChatProvider } from '@/components/chat/ChatProvider'
import { FloatingChatButton } from '@/components/chat/FloatingChatButton'
import { ChatPanel } from '@/components/chat/ChatPanel'

export function ChatWrapper({ children }: { children: React.ReactNode }) {
  return (
    <ChatProvider>
      {children}
      <ChatPanel />
      <FloatingChatButton />
    </ChatProvider>
  )
}
