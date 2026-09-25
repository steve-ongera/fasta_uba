/**
 * src/components/layout/Navbar.jsx
 */

import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export default function Navbar() {
  const { isAuthenticated, user, logout, isDriver } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <header className="ff-navbar">
      <Link to="/" className="ff-navbar__brand">
        Fasta<span>Fasta</span>
      </Link>

      <nav className="ff-navbar__links">
        {!isAuthenticated && (
          <>
            <Link to="/login">Log in</Link>
            <Link to="/register" className="ff-btn ff-btn--primary ff-btn--sm">
              Sign up
            </Link>
          </>
        )}

        {isAuthenticated && (
          <>
            <Link to={isDriver ? "/driver" : "/rider"}>Dashboard</Link>
            <Link to={isDriver ? "/driver/earnings" : "/rider/history"}>
              {isDriver ? "Earnings" : "History"}
            </Link>
            <span className="ff-navbar__user">Hi, {user?.first_name || user?.username}</span>
            <button className="ff-btn ff-btn--ghost ff-btn--sm" onClick={handleLogout}>
              Log out
            </button>
          </>
        )}
      </nav>
    </header>
  );
}
