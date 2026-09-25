/**
 * src/pages/rider/RiderDashboard.jsx
 * Booking flow: pick pickup/dropoff (search or map click) -> see fare
 * estimate per vehicle type -> request trip -> redirected to live tracking
 * once a driver is matched. Also redirects here-to-tracking if the rider
 * already has an active trip (e.g. they refreshed the page).
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import LocationSearchInput from "../../components/map/LocationSearchInput.jsx";
import MapView from "../../components/map/MapView.jsx";
import { fareAPI, tripAPI } from "../../services/api";
import { formatCurrency, getCurrentPosition, VEHICLE_TYPES } from "../../services/maps";

export default function RiderDashboard() {
  const navigate = useNavigate();

  const [pickup, setPickup] = useState(null); // {address, lat, lng}
  const [dropoff, setDropoff] = useState(null);
  const [pickupText, setPickupText] = useState("");
  const [dropoffText, setDropoffText] = useState("");
  const [settingPin, setSettingPin] = useState("pickup"); // which field a map click sets

  const [vehicleType, setVehicleType] = useState("ECONOMY");
  const [paymentMethod, setPaymentMethod] = useState("CASH");
  const [estimate, setEstimate] = useState(null);
  const [estimating, setEstimating] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState("");

  // check for an already-active trip and jump straight to tracking
  useEffect(() => {
    tripAPI.active().then((trip) => {
      if (trip) navigate(`/rider/trip/${trip.id}`, { replace: true });
    });
  }, [navigate]);

  // default pickup to current location
  useEffect(() => {
    getCurrentPosition()
      .then((pos) => {
        setPickup((p) => p || { ...pos, address: "Current location" });
        setPickupText((t) => t || "Current location");
      })
      .catch(() => {
        /* user can still search manually */
      });
  }, []);

  // re-estimate fare whenever both points or vehicle type change
  useEffect(() => {
    if (!pickup || !dropoff) {
      setEstimate(null);
      return;
    }
    setEstimating(true);
    setError("");
    fareAPI
      .estimate({
        pickup_lat: pickup.lat,
        pickup_lng: pickup.lng,
        dropoff_lat: dropoff.lat,
        dropoff_lng: dropoff.lng,
        vehicle_type: vehicleType,
      })
      .then(setEstimate)
      .catch(() => setError("Could not estimate fare. Try again."))
      .finally(() => setEstimating(false));
  }, [pickup, dropoff, vehicleType]);

  const handleMapClick = (latLng) => {
    if (settingPin === "pickup") {
      setPickup({ ...latLng, address: "Dropped pin" });
      setPickupText("Dropped pin");
      setSettingPin("dropoff");
    } else {
      setDropoff({ ...latLng, address: "Dropped pin" });
      setDropoffText("Dropped pin");
    }
  };

  const handleRequestRide = async () => {
    if (!pickup || !dropoff) return;
    setRequesting(true);
    setError("");
    try {
      const trip = await tripAPI.request({
        pickup_address: pickup.address,
        pickup_lat: pickup.lat,
        pickup_lng: pickup.lng,
        dropoff_address: dropoff.address,
        dropoff_lat: dropoff.lat,
        dropoff_lng: dropoff.lng,
        vehicle_type: vehicleType,
        payment_method: paymentMethod,
      });
      navigate(`/rider/trip/${trip.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not request a ride right now.");
    } finally {
      setRequesting(false);
    }
  };

  return (
    <div className="ff-booking">
      <div className="ff-booking__panel">
        <h1>Where to?</h1>

        <div className="ff-booking__inputs">
          <div className="ff-booking__input-row" onFocus={() => setSettingPin("pickup")}>
            <span className="ff-dot ff-dot--pickup" />
            <LocationSearchInput
              placeholder="Pickup location"
              value={pickupText}
              onChange={setPickupText}
              onSelect={(loc) => {
                setPickup(loc);
                setPickupText(loc.address);
              }}
            />
          </div>
          <div className="ff-booking__input-row" onFocus={() => setSettingPin("dropoff")}>
            <span className="ff-dot ff-dot--drop" />
            <LocationSearchInput
              placeholder="Where are you going?"
              value={dropoffText}
              onChange={setDropoffText}
              onSelect={(loc) => {
                setDropoff(loc);
                setDropoffText(loc.address);
              }}
            />
          </div>
          <p className="ff-booking__hint">
            Tip: you can also tap the map to set your {settingPin === "pickup" ? "pickup" : "drop-off"} point.
          </p>
        </div>

        {pickup && dropoff && (
          <div className="ff-vehicle-list">
            {VEHICLE_TYPES.map((v) => (
              <button
                key={v.value}
                className={`ff-vehicle-option ${vehicleType === v.value ? "active" : ""}`}
                onClick={() => setVehicleType(v.value)}
                type="button"
              >
                <span className="ff-vehicle-option__icon">{v.icon}</span>
                <span className="ff-vehicle-option__label">
                  <strong>{v.label}</strong>
                  <small>{v.description}</small>
                </span>
                {estimate && vehicleType === v.value && (
                  <span className="ff-vehicle-option__price">{formatCurrency(estimate.estimated_fare)}</span>
                )}
              </button>
            ))}
          </div>
        )}

        {estimating && <p className="ff-booking__estimating">Calculating fare…</p>}

        {estimate && (
          <div className="ff-fare-summary">
            <div>
              <span>Distance</span>
              <strong>{estimate.distance_km} km</strong>
            </div>
            <div>
              <span>ETA</span>
              <strong>{Math.round(estimate.duration_min)} min</strong>
            </div>
            <div>
              <span>Estimated fare</span>
              <strong>{formatCurrency(estimate.estimated_fare)}</strong>
            </div>
          </div>
        )}

        <div className="ff-payment-select">
          <span>Pay with</span>
          <div className="ff-payment-select__options">
            {["CASH", "WALLET", "CARD"].map((m) => (
              <button
                key={m}
                type="button"
                className={paymentMethod === m ? "active" : ""}
                onClick={() => setPaymentMethod(m)}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {error && <div className="ff-alert ff-alert--error">{error}</div>}

        <button
          className="ff-btn ff-btn--primary ff-btn--block ff-btn--lg"
          disabled={!pickup || !dropoff || requesting || estimating}
          onClick={handleRequestRide}
        >
          {requesting ? "Requesting…" : estimate ? `Request ${vehicleType}` : "Set pickup & drop-off"}
        </button>
      </div>

      <div className="ff-booking__map">
        <MapView pickup={pickup} dropoff={dropoff} onMapClick={handleMapClick} />
      </div>
    </div>
  );
}
