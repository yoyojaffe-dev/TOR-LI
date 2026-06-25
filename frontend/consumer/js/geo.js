// Location resolution: GPS (HTML5) + manual address geocoding (Google Maps).
import { loadGoogleMaps } from "./map.js";

// Browser geolocation -> {lat, lng} for the radius search.

export function getCurrentPosition(options = {}) {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("Geolocation not supported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        // Null-island (0,0) means the browser has no location data — treat as failure.
        if (lat === 0 && lng === 0) {
          reject(new Error("Geolocation returned null-island (0,0)"));
          return;
        }
        resolve({ lat, lng });
      },
      (err) => reject(err),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000, ...options }
    );
  });
}

// Convert a typed address/city into {lat, lng} via the Google Geocoder.
// Region-biased to Israel. Rejects if the query yields no results.
export async function geocodeAddress(query) {
  const trimmed = (query || "").trim();
  if (!trimmed) throw new Error("Empty address");

  const maps = await loadGoogleMaps();
  const geocoder = new maps.Geocoder();

  return new Promise((resolve, reject) => {
    geocoder.geocode({ address: trimmed, region: "il" }, (results, status) => {
      if (status === "OK" && results && results.length > 0) {
        const loc = results[0].geometry.location;
        resolve({
          lat: loc.lat(),
          lng: loc.lng(),
          label: results[0].formatted_address,
        });
      } else {
        reject(new Error(`Geocode failed (${status}) for "${trimmed}"`));
      }
    });
  });
}
