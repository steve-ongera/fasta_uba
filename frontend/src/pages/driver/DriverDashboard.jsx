/**
 * src/pages/driver/DriverDashboard.jsx
 * Driver's home screen: toggle online/offline, stream location while
 * online (watchPosition -> REST + WebSocket), and surface incoming
 * TripOffers with an accept/decline countdown.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import MapView from "../../components/map/MapView.jsx";
import { driverAPI, tripAPI } from "../../services/api";
import { formatCurrency, watchPosition } from "../../services/maps";
import { userSocket } from "../../services/socket";

const OFFER_TIMEOUT_SECONDS = 15;

export default function DriverDashboard() {
  const navigate = useNavigate();
  const stopWatchRef = useRef(null);

  const [isOnline, setIsOnline] = useState(false);
  const [position, setPosition] = useState(null);
  const [offer, setOffer] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(OFFER_TIMEOUT_SECONDS);
  const [responding, setResponding] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState("");

  // if already on a trip, jump straight to it
  useEffect(() => {
    tripAPI.active().then((trip) => {
      if (trip && ["ACCEPTED", "ARRIVED", "IN_PROGRESS"].includes(trip.status)) {
        navigate(`/driver/trip/${trip.id}`, { replace: true });
      }
    });
  }, [navigate]);

  // listen for pushed ride offers via the user-level notification socket
  useEffect(() => {
    const off = userSocket.on("ride_offer", (data) => {
      setOffer(data.offer);
      setSecondsLeft(OFFER_TIMEOUT_SECONDS);
    });
    return off;
  }, []);

  // fallback: poll for a pending offer every few seconds while online
  useEffect(() => {
    if (!isOnline) return;
    const interval = setInterval(() => {
      driverAPI.pendingOffer().then((o) => {
        if (o && (!offer || o.id !== offer.id)) {
          setOffer(o);
          setSecondsLeft(OFFER_TIMEOUT_SECONDS);
        }
      });
    }, 4000);
    return () => clearInterval(interval);
  }, [isOnline, offer]);

  // countdown + auto-decline
  useEffect(() => {
    if (!offer) return;
    if (secondsLeft <= 0) {
      handleRespond("decline");
      return;
    }
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offer, secondsLeft]);

  const startLocationStream = useCallback(() => {
    stopWatchRef.current = watchPosition(
      (pos) => {
        setPosition(pos);
        driverAPI.updateLocation(pos.lat, pos.lng, pos.heading || 0).catch(() => {});
      },
      () => setError("Couldn't access your location. Enable GPS to go online.")
    );
  }, []);

  const handleToggleOnline = async () => {
    setToggling(true);
    setError("");
    try {
      const newStatus = isOnline ? "OFFLINE" : "ONLINE";
      await driverAPI.setStatus(newStatus);
      setIsOnline(!isOnline);
      if (newStatus === "ONLINE") {
        startLocationStream();
      } else {
        stopWatchRef.current?.();
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Could not update status.");
    } finally {
      setToggling(false);
    }
  };

  const handleRespond = async (action) => {
    if (!offer || responding) return;
    setResponding(true);
    try {
      const result = await driverAPI.respondToOffer(offer.id, action);
      if (action === "accept" && result?.id) {
        navigate(`/driver/trip/${result.id}`);
      }
    } finally {
      setOffer(null);
      setResponding(false);
    }
  };

  useEffect(() => () => stopWatchRef.current?.(), []);

  return (
    <div className="ff-driver-dashboard">
      <div className="ff-driver-dashboard__panel">
        <div className="ff-online-toggle">
          <div>
            <h2>{isOnline ? "You're online" : "You're offline"}</h2>
            <p>{isOnline ? "Looking for ride requests nearby…" : "Go online to start receiving requests."}</p>
          </div>
          <button
            className={`ff-switch ${isOnline ? "on" : ""}`}
            onClick={handleToggleOnline}
            disabled={toggling}
            aria-label="Toggle online status"
          >
            <span className="ff-switch__thumb" />
          </button>
        </div>

        {error && <div className="ff-alert ff-alert--error">{error}</div>}

        {offer && (
          <div className="ff-offer-card">
            <div className="ff-offer-card__timer">
              <svg viewBox="0 0 36 36">
                <path
                  className="ff-offer-card__timer-bg"
                  d="M18 2 a 16 16 0 0 1 0 32 a 16 16 0 0 1 0 -32"
                />
                <path
                  className="ff-offer-card__timer-fg"
                  strokeDasharray={`${(secondsLeft / OFFER_TIMEOUT_SECONDS) * 100}, 100`}
                  d="M18 2 a 16 16 0 0 1 0 32 a 16 16 0 0 1 0 -32"
                />
              </svg>
              <span>{secondsLeft}s</span>
            </div>

            <h3>New ride request</h3>
            <p>Pickup is {offer.distance_to_pickup_km} km away</p>
            <p className="ff-offer-card__addr">{offer.trip?.pickup_address}</p>
            <p className="ff-offer-card__addr ff-offer-card__addr--drop">{offer.trip?.dropoff_address}</p>
            <div className="ff-offer-card__fare">{formatCurrency(offer.trip?.estimated_fare)}</div>

            <div className="ff-offer-card__actions">
              <button
                className="ff-btn ff-btn--danger ff-btn--block"
                onClick={() => handleRespond("decline")}
                disabled={responding}
              >
                Decline
              </button>
              <button
                className="ff-btn ff-btn--primary ff-btn--block"
                onClick={() => handleRespond("accept")}
                disabled={responding}
              >
                Accept
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="ff-driver-dashboard__map">
        <MapView center={position} zoom={15} driverPosition={position} />
      </div>
    </div>
  );
}
