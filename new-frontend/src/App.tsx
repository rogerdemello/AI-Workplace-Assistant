import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ChatProvider } from "@/contexts/ChatContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { ChatWidget } from "@/components/chat/ChatWidget";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Employee from "./pages/Employee";
import Dashboard from "./pages/Dashboard";
import ChatPage from "./pages/ChatPage";
import Tickets from "./pages/Tickets";
import Employees from "./pages/Employees";
import EmployeeProfile from "./pages/EmployeeProfile";
import Manager from "./pages/Manager";
import Surveys from "./pages/Surveys";
import EmailAssistant from "./pages/EmailAssistant";
import Admin from "./pages/Admin";
import Billing from "./pages/Billing";
import KnowledgeBase from "./pages/KnowledgeBase";
import OAuthCallback from "./pages/OAuthCallback";
import Rooms from "./pages/Rooms";
import NotFound from "./pages/NotFound.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <AuthProvider>
        <ChatProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route
                path="/employee"
                element={
                  <ProtectedRoute roles={["employee"]}>
                    <Employee />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute roles={["hr"]}>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/chat"
                element={
                  <ProtectedRoute>
                    <ChatPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tickets"
                element={
                  <ProtectedRoute>
                    <Tickets />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/employees"
                element={
                  <ProtectedRoute roles={["hr"]}>
                    <Employees />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/employees/:id"
                element={
                  <ProtectedRoute>
                    <EmployeeProfile />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/manager"
                element={
                  <ProtectedRoute roles={["manager", "hr"]}>
                    <Manager />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/surveys"
                element={
                  <ProtectedRoute>
                    <Surveys />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/email-assistant"
                element={
                  <ProtectedRoute roles={["hr"]}>
                    <EmailAssistant />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/knowledge-base"
                element={
                  <ProtectedRoute roles={["hr"]}>
                    <KnowledgeBase />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin"
                element={
                  <ProtectedRoute roles={["hr"]}>
                    <Admin />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/billing"
                element={
                  <ProtectedRoute roles={["hr"]}>
                    <Billing />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/rooms"
                element={
                  <ProtectedRoute>
                    <Rooms />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/oauth/callback/:provider"
                element={
                  <ProtectedRoute>
                    <OAuthCallback />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Routes>
            <ChatWidget />
          </BrowserRouter>
        </ChatProvider>
      </AuthProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
