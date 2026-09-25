/**
 * src/pages/rider/RideTracking.jsx
 * Live view of an active trip: status bar (matched/arriving/in-progress),
 * driver info card, live map with driver marker moving in real time via
 * TripSocket, cancel button, and a rating prompt once completed.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import MapView from "../../components/map/MapView.jsx";
import { ratingAPI, tripAPI } from "../../services/api";
import { TripSocket } from "../../services/socket";
import { decodePolyline, formatCurrency } from "../../services/maps";

const STATUS_LABEL = {
  REQUESTED: "Finding you a driver…",
  ACCEPTED: "Your driver is on the way",
  ARRIVED: "Your driver has arrived",
  IN_PROGRESS: "On trip",
  COMPLETED: "Trip completed",
  CANCELLED_BY_RIDER: "Trip cancelled",
  CANCELLED_BY_DRIVER: "Trip cancelled by driver",
  NO_DRIVERS_FOUND: "No drivers available nearby",
};

export default function RideTracking() {
  const { tripId } = useParams();
  const navigate = useNavigate();
  const socketRef = useRef(null);

  const [trip, setTrip] = useState(null);
  const [driverPos, setDriverPos] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [rating, setRating] = useState(5);
  const [ratingSubmitted, setRatingSubmitted] = useState(false);

  useEffect(() => {
    tripAPI.detail(tripId).then((t) => {
      setTrip(t);
      if (t.driver) setDriverPos({ lat: t.driver.current_lat, lng: t.driver.current_lng });
      setLoading(false);
    });

    const socket = new TripSocket(tripId).connect();
    socketRef.current = socket;

    const offStatus = socket.on("trip_update", (data) => setTrip((t) => ({ ...t, ...data.trip })));
    const offLoc = socket.on("driver_location", (data) =>
      setDriverPos({ lat: data.lat, lng: data.lng, heading: data.heading })
    );

    return () => {
      offStatus();
      offLoc();
      socket.disconnect();
    };
  }, [tripId]);

  const handleCancel = async () => {
    setCancelling(true);
    try {
      const updated = await tripAPI.cancel(tripId, "Rider cancelled");
      setTrip(updated);
    } finally {
      setCancelling(false);
    }
  };

  const handleRate = async () => {
    await ratingAPI.rate(tripId, rating);
    setRatingSubmitted(true);
    setTimeout(() => navigate("/rider"), 1500);
  };

  if (loading || !trip) {
    return <div className="ff-page-loading">Loading trip…</div>;
  }

  const routePoints = decodePolyline(trip.polyline);
  const canCancel = ["REQUESTED", "ACCEPTED"].includes(trip.status);
  const isTerminal = ["COMPLETED", "CANCELLED_BY_RIDER", "CANCELLED_BY_DRIVER", "NO_DRIVERS_FOUND"].includes(
    trip.status
  );

  return (
    <div className="ff-tracking">
      <div className="ff-tracking__panel">
        <div className={`ff-status-bar ff-status-bar--${trip.status.toLowerCase()}`}>
          {STATUS_LABEL[trip.status] || trip.status}
        </div>

        {trip.driver && (
          <div className="ff-driver-card">
            {trip.driver.photo ? (
              <img src={trip.driver.photo} alt={trip.driver.name} className="ff-driver-card__photo" />
            ) : (
              <div className="ff-driver-card__avatar">{trip.driver.name?.[0] || "D"}</div>
            )}
            <div className="ff-driver-card__info">
              <strong>{trip.driver.name}</strong>
              <span>★ {trip.driver.rating_avg}</span>
              <span>
                {trip.driver.vehicle?.color} {trip.driver.vehicle?.make} {trip.driver.vehicle?.model} —{" "}
                {trip.driver.vehicle?.plate_number}
              </span>
            </div>
            <a href={`tel:${trip.driver.phone_number}`} className="ff-btn ff-btn--outline ff-btn--sm">
              Call
            </a>
          </div>
        )}

        <div className="ff-trip-route">
          <div>
            <span className="ff-dot ff-dot--pickup" /> {trip.pickup_address}
          </div>
          <div>
            <span className="ff-dot ff-dot--drop" /> {trip.dropoff_address}
          </div>
        </div>

        <div className="ff-fare-summary">
          <div>
            <span>Estimated fare</span>
            <strong>{formatCurrency(trip.estimated_fare)}</strong>
          </div>
          {trip.final_fare && (
            <div>
              <span>Final fare</span>
              <strong>{formatCurrency(trip.final_fare)}</strong>
            </div>
          )}
        </div>

        {canCancel && (
          <button className="ff-btn ff-btn--danger ff-btn--block" onClick={handleCancel} disabled={cancelling}>
            {cancelling ? "Cancelling…" : "Cancel ride"}
          </button>
        )}

        {trip.status === "COMPLETED" && !ratingSubmitted && (
          <div className="ff-rate-card">
            <h3>Rate your driver</h3>
            <div className="ff-star-picker">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  className={n <= rating ? "active" : ""}
                  onClick={() => setRating(n)}
                  type="button"
                >
                  ★
                </button>
              ))}
            </div>
            <button className="ff-btn ff-btn--primary ff-btn--block" onClick={handleRate}>
              Submit rating
            </button>
          </div>
        )}

        {ratingSubmitted && <p className="ff-alert ff-alert--success">Thanks for rating your trip!</p>}

        {isTerminal && trip.status !== "COMPLETED" && (
          <button className="ff-btn ff-btn--primary ff-btn--block" onClick={() => navigate("/rider")}>
            Book another ride
          </button>
        )}
      </div>

      <div className="ff-tracking__map">
        <MapView
          pickup={{ lat: trip.pickup_lat, lng: trip.pickup_lng }}
          dropoff={{ lat: trip.dropoff_lat, lng: trip.dropoff_lng }}
          driverPosition={driverPos}
          routePoints={routePoints}
        />
      </div>
    </div>
  );
}
