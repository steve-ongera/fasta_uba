/**
 * src/services/maps.js
 * Google Maps loader + small geo helpers shared by MapView, LocationSearchInput,
 * and the booking flow. Uses @react-google-maps/api's useJsApiLoader in
 * components; this file holds the plain (non-React) helpers.
 */

export const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

export const GOOGLE_MAPS_LIBRARIES = ["places", "geometry"];

export const DEFAULT_CENTER = { lat: -1.286389, lng: 36.817223 }; // Nairobi fallback
export const DEFAULT_ZOOM = 14;

/** Wraps navigator.geolocation in a promise. */
export function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported by this browser."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) => reject(err),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    );
  });
}

/** Watches position continuously — used by the driver app while ONLINE. Returns a cleanup fn. */
export function watchPosition(onUpdate, onError) {
  if (!navigator.geolocation) {
    onError?.(new Error("Geolocation is not supported by this browser."));
    return () => {};
  }
  const watchId = navigator.geolocation.watchPosition(
    (pos) =>
      onUpdate({
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        heading: pos.coords.heading,
        speed: pos.coords.speed,
      }),
    onError,
    { enableHighAccuracy: true, maximumAge: 2000, timeout: 15000 }
  );
  return () => navigator.geolocation.clearWatch(watchId);
}

/** Haversine distance in km — mirrors backend/api/services.py for instant UI feedback before the API responds. */
export function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.asin(Math.sqrt(a));
}

/** Decodes a Google encoded polyline string into an array of {lat, lng} points, for drawing the route. */
export function decodePolyline(encoded) {
  if (!encoded) return [];
  let index = 0,
    lat = 0,
    lng = 0;
  const points = [];

  while (index < encoded.length) {
    let b,
      shift = 0,
      result = 0;
    do {
      b = encoded.charCodeAt(index++) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);
    lat += result & 1 ? ~(result >> 1) : result >> 1;

    shift = 0;
    result = 0;
    do {
      b = encoded.charCodeAt(index++) - 63;
      result |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);
    lng += result & 1 ? ~(result >> 1) : result >> 1;

    points.push({ lat: lat / 1e5, lng: lng / 1e5 });
  }
  return points;
}

export function formatCurrency(amount, currency = "KES") {
  if (amount == null) return "—";
  return new Intl.NumberFormat("en-KE", { style: "currency", currency, maximumFractionDigits: 0 }).format(
    amount
  );
}

export const VEHICLE_TYPES = [
  { value: "ECONOMY", label: "Economy", icon: "🚗", description: "Affordable everyday rides" },
  { value: "COMFORT", label: "Comfort", icon: "🚙", description: "Newer cars, extra legroom" },
  { value: "XL", label: "XL", icon: "🚐", description: "Bigger groups, up to 6" },
  { value: "BODA", label: "Boda Boda", icon: "🏍️", description: "Fast through traffic" },
];
