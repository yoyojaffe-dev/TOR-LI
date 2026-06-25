// Google Maps rendering: user position, radius circle, barbershop markers.
import { config } from "./config.js";

let mapsPromise = null;

// Lazy-load the Google Maps JS SDK once.
export function loadGoogleMaps() {
  if (mapsPromise) return mapsPromise;
  mapsPromise = new Promise((resolve, reject) => {
    if (window.google?.maps) {
      resolve(window.google.maps);
      return;
    }
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${config.GOOGLE_MAPS_API_KEY}&libraries=marker`;
    script.async = true;
    script.onload = () => resolve(window.google.maps);
    script.onerror = () => reject(new Error("Failed to load Google Maps"));
    document.head.appendChild(script);
  });
  return mapsPromise;
}

// Render the map into `el`, centered on the user, with a radius circle.
export async function renderMap(el, { lat, lng }, radiusM = config.DEFAULT_RADIUS_M) {
  const maps = await loadGoogleMaps();
  const map = new maps.Map(el, { center: { lat, lng }, zoom: 14 });

  new maps.Marker({ position: { lat, lng }, map, title: "You" });
  const circle = new maps.Circle({
    map,
    center: { lat, lng },
    radius: radiusM,
    fillColor: "#4285F4",
    fillOpacity: 0.1,
    strokeColor: "#4285F4",
    strokeOpacity: 0.4,
  });
  map.fitBounds(circle.getBounds());
  return map;
}

// Drop markers for a list of barbershops; returns the marker array.
export function renderBarbershopMarkers(map, barbershops, onSelect) {
  return barbershops
    .filter((b) => b.lat != null && b.lng != null)
    .map((b) => {
      const marker = new window.google.maps.Marker({
        position: { lat: b.lat, lng: b.lng },
        map,
        title: b.name,
      });
      if (onSelect) marker.addListener("click", () => onSelect(b));
      return marker;
    });
}
