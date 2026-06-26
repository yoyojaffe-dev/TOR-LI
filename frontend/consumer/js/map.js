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

// Dark map style matching the app's dark theme + gold accent.
const DARK_STYLE = [
  { elementType: "geometry",            stylers: [{ color: "#1a1a2e" }] },
  { elementType: "labels.text.fill",    stylers: [{ color: "#8e8ea0" }] },
  { elementType: "labels.text.stroke",  stylers: [{ color: "#1a1a2e" }] },
  { featureType: "road", elementType: "geometry",           stylers: [{ color: "#2d2d44" }] },
  { featureType: "road", elementType: "geometry.stroke",    stylers: [{ color: "#1a1a2e" }] },
  { featureType: "road.arterial",  elementType: "labels.text.fill", stylers: [{ color: "#8e8ea0" }] },
  { featureType: "road.highway",   elementType: "geometry",         stylers: [{ color: "#3d3d5c" }] },
  { featureType: "water",          elementType: "geometry",         stylers: [{ color: "#0d1b2a" }] },
  { featureType: "water",          elementType: "labels.text.fill", stylers: [{ color: "#3d5a80" }] },
  { featureType: "poi",            stylers: [{ visibility: "off" }] },
  { featureType: "transit",        stylers: [{ visibility: "off" }] },
  { featureType: "administrative", elementType: "geometry", stylers: [{ color: "#2d2d44" }] },
  { featureType: "administrative.country", elementType: "labels.text.fill", stylers: [{ color: "#9e9e9e" }] },
];

// Render the map into `el`, centered on the user, with a radius circle.
// zoom: 15 (street-level). fitBounds removed — it zoomed out too far with many shops.
export async function renderMap(el, { lat, lng }, radiusM = config.DEFAULT_RADIUS_M) {
  const maps = await loadGoogleMaps();
  const map = new maps.Map(el, {
    center: { lat, lng },
    zoom: 15,
    styles: DARK_STYLE,
    disableDefaultUI: true,
    zoomControl: true,
    zoomControlOptions: { position: maps.ControlPosition.LEFT_BOTTOM },
  });

  // User location: blue dot (distinct from gold barbershop pins).
  const userMarker = new maps.Marker({
    position: { lat, lng },
    map,
    title: "You",
    zIndex: 999,
    icon: {
      path: maps.SymbolPath.CIRCLE,
      scale: 8,
      fillColor: "#4285F4",
      fillOpacity: 1,
      strokeColor: "#ffffff",
      strokeWeight: 3,
    },
  });
  const circle = new maps.Circle({
    map,
    center: { lat, lng },
    radius: radiusM,
    fillColor: "#EFB200",
    fillOpacity: 0.05,
    strokeColor: "#EFB200",
    strokeOpacity: 0.3,
    strokeWeight: 1,
  });

  // Stash for later recentering.
  map.__torli = { userMarker, circle, radiusM };
  return map;
}

// Recenter an existing map on a new location, moving the user marker + circle.
export function recenterMap(map, { lat, lng }) {
  if (!map) return;
  const center = { lat, lng };
  map.setCenter(center);
  const refs = map.__torli;
  if (refs) {
    refs.userMarker.setPosition(center);
    refs.circle.setCenter(center);
  }
}

// Travel ETAs from origin -> dest for the 4 modes. Each mode is independent so
// one failing (e.g. TRANSIT with no routes) doesn't break the others.
// Returns { driving, walking, bicycling, transit } each {distanceKm, durationText} | null.
export async function travelEtas(origin, dest) {
  const maps = await loadGoogleMaps();
  const svc = new maps.DistanceMatrixService();
  const modes = {
    driving:   maps.TravelMode.DRIVING,
    walking:   maps.TravelMode.WALKING,
    bicycling: maps.TravelMode.BICYCLING,
    transit:   maps.TravelMode.TRANSIT,
  };

  const one = (travelMode) =>
    new Promise((resolve) => {
      const req = {
        origins: [origin],
        destinations: [dest],
        travelMode,
        unitSystem: maps.UnitSystem.METRIC,
      };
      if (travelMode === maps.TravelMode.TRANSIT) {
        req.transitOptions = { departureTime: new Date() };
      }
      svc.getDistanceMatrix(req, (res, status) => {
        if (status !== "OK") return resolve(null);
        const el = res?.rows?.[0]?.elements?.[0];
        if (!el || el.status !== "OK") return resolve(null);
        resolve({
          distanceKm: el.distance ? (el.distance.value / 1000).toFixed(1) : null,
          durationText: el.duration ? el.duration.text : null,
        });
      });
    });

  const [driving, walking, bicycling, transit] = await Promise.all([
    one(modes.driving), one(modes.walking), one(modes.bicycling), one(modes.transit),
  ]);
  return { driving, walking, bicycling, transit };
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
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 7,
          fillColor: "#EFB200",
          fillOpacity: 0.9,
          strokeColor: "#1a1a2e",
          strokeWeight: 1.5,
        },
      });
      if (onSelect) marker.addListener("click", () => onSelect(b));
      return marker;
    });
}
