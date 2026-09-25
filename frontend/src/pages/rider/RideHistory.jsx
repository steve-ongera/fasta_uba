import { useEffect, useState } from "react";
import { tripAPI } from "../../services/api";
import { formatCurrency } from "../../services/maps";

export default function RideHistory() {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    tripAPI
      .history()
      .then((data) => setTrips(data.results || data))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="ff-page-loading">Loading trips…</div>;

  return (
    <div className="ff-page">
      <h1>Your trips</h1>
      <div className="ff-trip-list">
        {trips.map((t) => (
          <div key={t.id} className="ff-trip-list__row">
            <div>
              <strong>{t.pickup_address}</strong>
              <span> → {t.dropoff_address}</span>
              <br />
              <small>{new Date(t.requested_at).toLocaleString()}</small>
            </div>
            <div>{formatCurrency(t.final_fare || t.estimated_fare)}</div>
            <div className={`ff-badge ff-badge--${t.status.toLowerCase()}`}>{t.status}</div>
          </div>
        ))}
        {trips.length === 0 && <p>No trips yet — go book your first ride!</p>}
      </div>
    </div>
  );
}
