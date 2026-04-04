import './globals.css'
import type { Metadata } from 'next'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { ChatWrapper } from '@/components/chat/ChatWrapper'

export const metadata: Metadata = {
  title: 'HR Assistant',
  description: 'AI-powered conversational assistant for HR automation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <ChatWrapper>
          <div className="min-h-screen bg-background">
            <header className="border-b">
              <div className="container mx-auto px-4 py-4">
                <div className="flex items-center justify-between">
                  <h1 className="text-2xl font-bold">HR Assistant</h1>
                  <nav className="flex gap-4">
                    <Link href="/">
                      <Button variant="ghost">Home</Button>
                    </Link>
                    <Link href="/chat">
                      <Button variant="ghost">Chat</Button>
                    </Link>
                    <Link href="/dashboard">
                      <Button variant="ghost">Dashboard</Button>
                    </Link>
                    <Link href="/tickets">
                      <Button variant="ghost">Tickets</Button>
                    </Link>
                    <Link href="/email-draft">
                      <Button variant="ghost">Email Draft</Button>
                    </Link>
                    <Link href="/surveys">
                      <Button variant="ghost">Surveys</Button>
                    </Link>
                    <Link href="/admin/users">
                      <Button variant="ghost">Admin</Button>
                    </Link>
                  </nav>
                </div>
              </div>
            </header>
            <main className="container mx-auto px-4 py-8">
              {children}
            </main>
          </div>
        </ChatWrapper>
      </body>
    </html>
  )
}
