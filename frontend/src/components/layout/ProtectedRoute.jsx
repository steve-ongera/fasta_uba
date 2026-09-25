/**
 * src/components/layout/ProtectedRoute.jsx
 * Gate routes behind auth, and optionally behind a specific role.
 */

import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export default function ProtectedRoute({ children, role }) {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="ff-page-loading">Loading…</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (role && user?.role !== role) {
    const home = user?.role === "DRIVER" ? "/driver" : "/rider";
    return <Navigate to={home} replace />;
  }

  return children;
}
