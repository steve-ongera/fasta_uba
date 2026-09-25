import { useEffect, useState } from "react";
import { driverAPI, tripAPI } from "../../services/api";
import { formatCurrency } from "../../services/maps";

export default function Earnings() {
  const [summary, setSummary] = useState(null);
  const [trips, setTrips] = useState([]);

  useEffect(() => {
    driverAPI.earnings().then(setSummary);
    tripAPI.history().then((data) => setTrips(data.results || data));
  }, []);

  return (
    <div className="ff-page">
      <h1>Earnings</h1>

      {summary && (
        <div className="ff-stats-grid">
          <div className="ff-stat-card">
            <span>Total earnings</span>
            <strong>{formatCurrency(summary.total_earnings)}</strong>
          </div>
          <div className="ff-stat-card">
            <span>Total trips</span>
            <strong>{summary.total_trips}</strong>
          </div>
          <div className="ff-stat-card">
            <span>Wallet balance</span>
            <strong>{formatCurrency(summary.wallet_balance)}</strong>
          </div>
          <div className="ff-stat-card">
            <span>Rating</span>
            <strong>★ {summary.rating_avg}</strong>
          </div>
        </div>
      )}

      <h2>Recent trips</h2>
      <div className="ff-trip-list">
        {trips.map((t) => (
          <div key={t.id} className="ff-trip-list__row">
            <div>
              <strong>{t.pickup_address}</strong>
              <span> → {t.dropoff_address}</span>
            </div>
            <div>{formatCurrency(t.final_fare || t.estimated_fare)}</div>
            <div className={`ff-badge ff-badge--${t.status.toLowerCase()}`}>{t.status}</div>
          </div>
        ))}
        {trips.length === 0 && <p>No trips yet.</p>}
      </div>
    </div>
  );
}
