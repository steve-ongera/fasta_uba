/**
 * src/components/map/MapView.jsx
 * Thin wrapper around @react-google-maps/api's <GoogleMap>, used everywhere
 * we show a map: booking screen, live tracking, driver dashboard.
 */

import { GoogleMap, Marker, Polyline, useJsApiLoader } from "@react-google-maps/api";
import { useCallback, useState } from "react";
import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  GOOGLE_MAPS_API_KEY,
  GOOGLE_MAPS_LIBRARIES,
} from "../../services/maps";

const containerStyle = { width: "100%", height: "100%" };

const mapOptions = {
  disableDefaultUI: true,
  zoomControl: true,
  clickableIcons: false,
  styles: [
    { featureType: "poi", elementType: "labels", stylers: [{ visibility: "off" }] },
    { featureType: "transit", elementType: "labels", stylers: [{ visibility: "off" }] },
  ],
};

/**
 * props:
 *  - pickup / dropoff: {lat, lng} | null
 *  - driverPosition: {lat, lng, heading} | null  (live-tracking view)
 *  - routePoints: [{lat,lng}, ...] | null         (decoded polyline)
 *  - onMapClick: (latLng) => void                 (booking screen: tap to set pin)
 *  - center, zoom: optional overrides
 */
export default function MapView({
  pickup,
  dropoff,
  driverPosition,
  routePoints,
  onMapClick,
  center,
  zoom,
}) {
  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: GOOGLE_MAPS_API_KEY,
    libraries: GOOGLE_MAPS_LIBRARIES,
  });
  const [map, setMap] = useState(null);

  const onLoad = useCallback((mapInstance) => setMap(mapInstance), []);
  const onUnmount = useCallback(() => setMap(null), []);

  const handleClick = (e) => {
    if (!onMapClick) return;
    onMapClick({ lat: e.latLng.lat(), lng: e.latLng.lng() });
  };

  if (!isLoaded) {
    return (
      <div className="ff-map ff-map--loading">
        <span>Loading map…</span>
      </div>
    );
  }

  return (
    <div className="ff-map">
      <GoogleMap
        mapContainerStyle={containerStyle}
        center={center || pickup || DEFAULT_CENTER}
        zoom={zoom || DEFAULT_ZOOM}
        options={mapOptions}
        onLoad={onLoad}
        onUnmount={onUnmount}
        onClick={handleClick}
      >
        {pickup && (
          <Marker
            position={pickup}
            label={{ text: "P", color: "#fff", fontSize: "11px", fontWeight: "700" }}
            icon={{
              path: window.google.maps.SymbolPath.CIRCLE,
              scale: 9,
              fillColor: "#16a34a",
              fillOpacity: 1,
              strokeColor: "#ffffff",
              strokeWeight: 2,
            }}
          />
        )}

        {dropoff && (
          <Marker
            position={dropoff}
            label={{ text: "D", color: "#fff", fontSize: "11px", fontWeight: "700" }}
            icon={{
              path: window.google.maps.SymbolPath.CIRCLE,
              scale: 9,
              fillColor: "#dc2626",
              fillOpacity: 1,
              strokeColor: "#ffffff",
              strokeWeight: 2,
            }}
          />
        )}

        {driverPosition && (
          <Marker
            position={driverPosition}
            icon={{
              path: "M12 2 L19 21 L12 17 L5 21 Z", // simple arrow glyph, rotated by heading
              scale: 1.6,
              fillColor: "#2563eb",
              fillOpacity: 1,
              strokeColor: "#ffffff",
              strokeWeight: 1,
              rotation: driverPosition.heading || 0,
              anchor: new window.google.maps.Point(12, 12),
            }}
          />
        )}

        {routePoints?.length > 1 && (
          <Polyline
            path={routePoints}
            options={{ strokeColor: "#111827", strokeOpacity: 0.85, strokeWeight: 4 }}
          />
        )}
      </GoogleMap>
    </div>
  );
}
