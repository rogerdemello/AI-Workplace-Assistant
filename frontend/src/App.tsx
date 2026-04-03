import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { Card, CardHeader, CardTitle, CardContent } from './components/ui/card'
import { Label } from './components/ui/label'
import { Textarea } from './components/ui/textarea'
import { Avatar } from './components/ui/avatar'
import { Badge } from './components/ui/badge'
import { TicketsPage } from './pages/TicketsPage'
import { EmailDraftPage } from './pages/EmailDraftPage'
import { SurveysPage } from './pages/SurveysPage'
import { DashboardPage } from './pages/DashboardPage'
import { AdminUsersPage } from './pages/AdminUsersPage'
import { ChatPage } from './pages/ChatPage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <header className="border-b">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-bold">HR Assistant</h1>
              <nav className="flex gap-4">
                <Link to="/">
                  <Button variant="ghost">Home</Button>
                </Link>
                <Link to="/chat">
                  <Button variant="ghost">Chat</Button>
                </Link>
                <Link to="/dashboard">
                  <Button variant="ghost">Dashboard</Button>
                </Link>
                <Link to="/tickets">
                  <Button variant="ghost">Tickets</Button>
                </Link>
                <Link to="/email-draft">
                  <Button variant="ghost">Email Draft</Button>
                </Link>
                <Link to="/surveys">
                  <Button variant="ghost">Surveys</Button>
                </Link>
                <Link to="/admin/users">
                  <Button variant="ghost">Admin</Button>
                </Link>
              </nav>
            </div>
          </div>
        </header>
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={
              <div className="space-y-6">
                <div className="text-center">Welcome to HR Assistant</div>
                
                <Card>
                  <CardHeader>
                    <CardTitle>Test Card</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label htmlFor="email">Email</Label>
                      <Input id="email" placeholder="Enter your email" />
                    </div>
                    <div>
                      <Label htmlFor="message">Message</Label>
                      <Textarea id="message" placeholder="Enter your message" />
                    </div>
                    <div className="flex gap-2">
                      <Button>Submit</Button>
                      <Button variant="secondary">Cancel</Button>
                      <Button variant="destructive">Delete</Button>
                    </div>
                    <div className="flex items-center gap-2">
                      <Avatar src="https://via.placeholder.com/40" alt="User" />
                      <Badge variant="default">Active</Badge>
                      <Badge variant="secondary">Pending</Badge>
                      <Badge variant="destructive">Error</Badge>
                      <Badge variant="outline">New</Badge>
                    </div>
                  </CardContent>
                </Card>
              </div>
            } />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/tickets" element={<TicketsPage />} />
            <Route path="/email-draft" element={<EmailDraftPage />} />
            <Route path="/surveys" element={<SurveysPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
