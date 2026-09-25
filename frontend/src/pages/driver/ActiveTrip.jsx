/**
 * src/pages/driver/ActiveTrip.jsx
 * Driver-side view of a matched trip: navigate to pickup -> Arrived ->
 * Start trip -> Complete trip, streaming location the whole time.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import MapView from "../../components/map/MapView.jsx";
import { tripAPI } from "../../services/api";
import { formatCurrency, watchPosition } from "../../services/maps";
import { TripSocket } from "../../services/socket";

const NEXT_ACTION = {
  ACCEPTED: { label: "I've arrived", call: (id) => tripAPI.arrive(id) },
  ARRIVED: { label: "Start trip", call: (id) => tripAPI.start(id) },
  IN_PROGRESS: { label: "Complete trip", call: (id) => tripAPI.complete(id) },
};

export default function ActiveTrip() {
  const { tripId } = useParams();
  const navigate = useNavigate();
  const stopWatchRef = useRef(null);
  const socketRef = useRef(null);

  const [trip, setTrip] = useState(null);
  const [position, setPosition] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    tripAPI.detail(tripId).then(setTrip);

    const socket = new TripSocket(tripId).connect();
    socketRef.current = socket;

    stopWatchRef.current = watchPosition((pos) => {
      setPosition(pos);
      socket.sendLocationUpdate(pos.lat, pos.lng, pos.heading || 0);
    });

    return () => {
      stopWatchRef.current?.();
      socket.disconnect();
    };
  }, [tripId]);

  const handleNextStep = async () => {
    if (!trip) return;
    const action = NEXT_ACTION[trip.status];
    if (!action) return;
    setBusy(true);
    try {
      const updated = await action.call(tripId);
      setTrip(updated);
      if (updated.status === "COMPLETED") {
        navigate("/driver");
      }
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    setBusy(true);
    try {
      await tripAPI.cancel(tripId, "Driver cancelled");
      navigate("/driver");
    } finally {
      setBusy(false);
    }
  };

  if (!trip) return <div className="ff-page-loading">Loading trip…</div>;

  const action = NEXT_ACTION[trip.status];

  return (
    <div className="ff-tracking">
      <div className="ff-tracking__panel">
        <div className={`ff-status-bar ff-status-bar--${trip.status.toLowerCase()}`}>{trip.status}</div>

        <div className="ff-driver-card">
          <div className="ff-driver-card__avatar">{trip.rider?.first_name?.[0] || "R"}</div>
          <div className="ff-driver-card__info">
            <strong>
              {trip.rider?.first_name} {trip.rider?.last_name}
            </strong>
            <span>{trip.payment_method}</span>
          </div>
          <a href={`tel:${trip.rider?.phone_number}`} className="ff-btn ff-btn--outline ff-btn--sm">
            Call
          </a>
        </div>

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
            <span>Fare</span>
            <strong>{formatCurrency(trip.estimated_fare)}</strong>
          </div>
        </div>

        {action && (
          <button className="ff-btn ff-btn--primary ff-btn--block ff-btn--lg" onClick={handleNextStep} disabled={busy}>
            {busy ? "Working…" : action.label}
          </button>
        )}

        {trip.status !== "IN_PROGRESS" && trip.status !== "COMPLETED" && (
          <button className="ff-btn ff-btn--danger ff-btn--block" onClick={handleCancel} disabled={busy}>
            Cancel trip
          </button>
        )}
      </div>

      <div className="ff-tracking__map">
        <MapView
          pickup={{ lat: trip.pickup_lat, lng: trip.pickup_lng }}
          dropoff={{ lat: trip.dropoff_lat, lng: trip.dropoff_lng }}
          driverPosition={position}
        />
      </div>
    </div>
  );
}
