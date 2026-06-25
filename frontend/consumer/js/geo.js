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
