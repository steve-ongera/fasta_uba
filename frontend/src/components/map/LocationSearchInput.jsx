/**
 * src/components/map/LocationSearchInput.jsx
 * Google Places Autocomplete text input. Calls onSelect({address, lat, lng})
 * when the user picks a suggestion.
 */

import { Autocomplete } from "@react-google-maps/api";
import { useRef } from "react";

export default function LocationSearchInput({ placeholder, value, onChange, onSelect }) {
  const autocompleteRef = useRef(null);

  const handlePlaceChanged = () => {
    const place = autocompleteRef.current?.getPlace();
    if (!place?.geometry) return;
    onSelect({
      address: place.formatted_address || place.name,
      lat: place.geometry.location.lat(),
      lng: place.geometry.location.lng(),
    });
  };

  return (
    <Autocomplete
      onLoad={(ac) => (autocompleteRef.current = ac)}
      onPlaceChanged={handlePlaceChanged}
      options={{ fields: ["formatted_address", "name", "geometry"] }}
    >
      <input
        className="ff-location-input"
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </Autocomplete>
  );
}
