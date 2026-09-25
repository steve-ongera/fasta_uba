/**
 * src/pages/LoginPage.jsx
 */

import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const user = await login(form.email, form.password);
      const redirectTo = location.state?.from?.pathname || (user.role === "DRIVER" ? "/driver" : "/rider");
      navigate(redirectTo, { replace: true });
    } catch (err) {
      const detail =
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.detail ||
        "Invalid email or password.";
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="ff-auth-page">
      <form className="ff-auth-card" onSubmit={handleSubmit}>
        <h1>Welcome back</h1>
        <p className="ff-auth-card__subtitle">Log in to request or drive a ride.</p>

        {error && <div className="ff-alert ff-alert--error">{error}</div>}

        <label className="ff-field">
          <span>Email</span>
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            required
            autoComplete="email"
            placeholder="you@example.com"
          />
        </label>

        <label className="ff-field">
          <span>Password</span>
          <input
            type="password"
            name="password"
            value={form.password}
            onChange={handleChange}
            required
            autoComplete="current-password"
            placeholder="••••••••"
          />
        </label>

        <button type="submit" className="ff-btn ff-btn--primary ff-btn--block" disabled={submitting}>
          {submitting ? "Logging in…" : "Log in"}
        </button>

        <p className="ff-auth-card__footer">
          New to FastaFasta? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </div>
  );
}
