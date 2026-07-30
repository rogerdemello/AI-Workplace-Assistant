import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { getDefaultRouteForRole, useAuth, type UserRole } from "@/contexts/AuthContext";

interface ProtectedRouteProps {
  children: ReactNode;
  /** If set, only these roles may access the route. */
  roles?: UserRole[];
}

export function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { session } = useAuth();
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (roles?.length && !roles.includes(session.role)) {
    return <Navigate to={getDefaultRouteForRole(session.role)} replace />;
  }

  return <>{children}</>;
}
