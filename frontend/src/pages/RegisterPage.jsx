/**
 * src/pages/RegisterPage.jsx
 * Single signup form that adapts: extra license/vehicle fields appear when
 * role = DRIVER, matching RegisterView + DriverRegistrationExtraSerializer
 * on the backend.
 */

import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { VEHICLE_TYPES } from "../services/maps";

const initialForm = {
  first_name: "",
  last_name: "",
  username: "",
  email: "",
  phone_number: "",
  password: "",
  password2: "",
  role: "RIDER",
  // driver-only
  license_number: "",
  license_expiry: "",
  vehicle_type: "ECONOMY",
  make: "",
  model: "",
  color: "",
  year: "",
  plate_number: "",
  capacity: 4,
};

export default function RegisterPage() {
  const [params] = useSearchParams();
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ ...initialForm, role: params.get("role") === "DRIVER" ? "DRIVER" : "RIDER" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (form.password !== form.password2) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const user = await register(form);
      navigate(user.role === "DRIVER" ? "/driver" : "/rider", { replace: true });
    } catch (err) {
      const data = err.response?.data;
      const firstError = data && typeof data === "object" ? Object.values(data)[0] : null;
      setError((Array.isArray(firstError) ? firstError[0] : firstError) || "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="ff-auth-page">
      <form className="ff-auth-card ff-auth-card--wide" onSubmit={handleSubmit}>
        <h1>Create your account</h1>

        <div className="ff-role-toggle">
          <button
            type="button"
            className={form.role === "RIDER" ? "active" : ""}
            onClick={() => setForm((f) => ({ ...f, role: "RIDER" }))}
          >
            I'm a Rider
          </button>
          <button
            type="button"
            className={form.role === "DRIVER" ? "active" : ""}
            onClick={() => setForm((f) => ({ ...f, role: "DRIVER" }))}
          >
            I'm a Driver
          </button>
        </div>

        {error && <div className="ff-alert ff-alert--error">{error}</div>}

        <div className="ff-field-row">
          <label className="ff-field">
            <span>First name</span>
            <input name="first_name" value={form.first_name} onChange={handleChange} required />
          </label>
          <label className="ff-field">
            <span>Last name</span>
            <input name="last_name" value={form.last_name} onChange={handleChange} required />
          </label>
        </div>

        <label className="ff-field">
          <span>Username</span>
          <input name="username" value={form.username} onChange={handleChange} required />
        </label>

        <div className="ff-field-row">
          <label className="ff-field">
            <span>Email</span>
            <input type="email" name="email" value={form.email} onChange={handleChange} required />
          </label>
          <label className="ff-field">
            <span>Phone number</span>
            <input name="phone_number" value={form.phone_number} onChange={handleChange} required placeholder="07XXXXXXXX" />
          </label>
        </div>

        <div className="ff-field-row">
          <label className="ff-field">
            <span>Password</span>
            <input type="password" name="password" value={form.password} onChange={handleChange} required />
          </label>
          <label className="ff-field">
            <span>Confirm password</span>
            <input type="password" name="password2" value={form.password2} onChange={handleChange} required />
          </label>
        </div>

        {form.role === "DRIVER" && (
          <fieldset className="ff-fieldset">
            <legend>Driver & vehicle details</legend>

            <div className="ff-field-row">
              <label className="ff-field">
                <span>License number</span>
                <input name="license_number" value={form.license_number} onChange={handleChange} required />
              </label>
              <label className="ff-field">
                <span>License expiry</span>
                <input type="date" name="license_expiry" value={form.license_expiry} onChange={handleChange} required />
              </label>
            </div>

            <label className="ff-field">
              <span>Vehicle type</span>
              <select name="vehicle_type" value={form.vehicle_type} onChange={handleChange}>
                {VEHICLE_TYPES.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.icon} {v.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="ff-field-row">
              <label className="ff-field">
                <span>Make</span>
                <input name="make" value={form.make} onChange={handleChange} required placeholder="Toyota" />
              </label>
              <label className="ff-field">
                <span>Model</span>
                <input name="model" value={form.model} onChange={handleChange} required placeholder="Axio" />
              </label>
            </div>

            <div className="ff-field-row">
              <label className="ff-field">
                <span>Color</span>
                <input name="color" value={form.color} onChange={handleChange} required />
              </label>
              <label className="ff-field">
                <span>Year</span>
                <input type="number" name="year" value={form.year} onChange={handleChange} required min="1990" max="2030" />
              </label>
              <label className="ff-field">
                <span>Plate number</span>
                <input name="plate_number" value={form.plate_number} onChange={handleChange} required placeholder="KDA 123X" />
              </label>
            </div>

            <label className="ff-field">
              <span>Seats</span>
              <input type="number" name="capacity" value={form.capacity} onChange={handleChange} min="1" max="14" />
            </label>
          </fieldset>
        )}

        <button type="submit" className="ff-btn ff-btn--primary ff-btn--block" disabled={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </button>

        <p className="ff-auth-card__footer">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
