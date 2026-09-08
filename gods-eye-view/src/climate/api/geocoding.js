/**
 * Climate Eye — Geographic Geocoding & Reverse Geocoding Utility
 *
 * Provides authoritative location search and reverse geocoding:
 * - Direct coordinate resolution for major planetary monitoring centers
 * - Open-Meteo forward geocoding (zero API keys required, global coverage)
 * - BigDataCloud client-side reverse geocoding (zero API keys required, returns City, Subdivision, Country)
 * - Graceful fallback to formatted coordinate representations when outside municipal bounds
 *
 * Browser-safe: pure ESM, native fetch, zero Node.js dependencies.
 */

export const KNOWN_REGIONS = Object.freeze({
  hyderabad: { name: 'Hyderabad', country: 'India', subdivision: 'Telangana', latitude: 17.3850, longitude: 78.4867 },
  mumbai: { name: 'Mumbai', country: 'India', subdivision: 'Maharashtra', latitude: 19.0760, longitude: 72.8777 },
  delhi: { name: 'Delhi', country: 'India', subdivision: 'National Capital Territory', latitude: 28.6139, longitude: 77.2090 },
  bengaluru: { name: 'Bengaluru', country: 'India', subdivision: 'Karnataka', latitude: 12.9716, longitude: 77.5946 },
  tokyo: { name: 'Tokyo', country: 'Japan', subdivision: 'Kanto', latitude: 35.6762, longitude: 139.6503 },
  california: { name: 'California', country: 'United States', subdivision: 'Central Valley', latitude: 36.7783, longitude: -119.4179 },
  london: { name: 'London', country: 'United Kingdom', subdivision: 'England', latitude: 51.5074, longitude: -0.1278 },
  'new york': { name: 'New York', country: 'United States', subdivision: 'New York', latitude: 40.7128, longitude: -74.0060 },
  paris: { name: 'Paris', country: 'France', subdivision: 'Île-de-France', latitude: 48.8566, longitude: 2.3522 },
  sydney: { name: 'Sydney', country: 'Australia', subdivision: 'New South Wales', latitude: -33.8688, longitude: 151.2093 },
});

const cache = new Map();

/**
 * Resolves a query string into geographic coordinates and location metadata.
 *
 * @param {string} query - Target place name (e.g. "Hyderabad", "Paris", "Tokyo")
 * @returns {Promise<{ name: string, country: string, subdivision: string, latitude: number, longitude: number } | null>}
 */
export async function geocodeLocation(query) {
  if (!query || typeof query !== 'string') return null;
  const clean = query.trim();
  if (clean.length < 2) return null;

  const cacheKey = `geo:${clean.toLowerCase()}`;
  if (cache.has(cacheKey)) return cache.get(cacheKey);

  // 1. Check known catalog
  const known = KNOWN_REGIONS[clean.toLowerCase()];
  if (known) {
    cache.set(cacheKey, known);
    return known;
  }

  // 2. Query Open-Meteo Geocoding API
  try {
    const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(clean)}&count=1&language=en&format=json`;
    const res = await fetch(url, { signal: AbortSignal.timeout(6000) });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.results) && data.results.length > 0) {
        const top = data.results[0];
        const result = {
          name: top.name || clean,
          country: top.country || 'Global Sector',
          subdivision: top.admin1 || top.country || '',
          latitude: Number(top.latitude),
          longitude: Number(top.longitude),
        };
        cache.set(cacheKey, result);
        return result;
      }
    }
  } catch (err) {
    // Open-Meteo fetch failed or timed out, attempt fallback
  }

  // 3. Fallback: OpenStreetMap Nominatim
  try {
    const nomUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(clean)}&limit=1`;
    const res = await fetch(nomUrl, {
      headers: { 'User-Agent': 'ClimateEyeCommandCenter/1.0' },
      signal: AbortSignal.timeout(6000),
    });
    if (res.ok) {
      const items = await res.json();
      if (Array.isArray(items) && items.length > 0) {
        const top = items[0];
        const parts = (top.display_name || '').split(',').map((s) => s.trim());
        const result = {
          name: parts[0] || clean,
          country: parts[parts.length - 1] || 'Global Sector',
          subdivision: parts.length > 2 ? parts[parts.length - 2] : '',
          latitude: parseFloat(top.lat),
          longitude: parseFloat(top.lon),
        };
        cache.set(cacheKey, result);
        return result;
      }
    }
  } catch (_) {}

  return null;
}

/**
 * Resolves a latitude and longitude pair into a human-readable city/region name.
 *
 * @param {number} latitude
 * @param {number} longitude
 * @returns {Promise<{ name: string, country: string, subdivision: string, latitude: number, longitude: number }>}
 */
export async function reverseGeocodeLocation(latitude, longitude) {
  const lat = Number(latitude);
  const lon = Number(longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return {
      name: 'Unknown Location',
      country: 'Global Sector',
      subdivision: '',
      latitude: 0,
      longitude: 0,
    };
  }

  const cacheKey = `rev:${lat.toFixed(3)},${lon.toFixed(3)}`;
  if (cache.has(cacheKey)) return cache.get(cacheKey);

  // 1. Proximity check against known catalog (< 50 km distance)
  for (const reg of Object.values(KNOWN_REGIONS)) {
    const dLat = Math.abs(reg.latitude - lat);
    const dLon = Math.abs(reg.longitude - lon);
    if (dLat < 0.45 && dLon < 0.45) {
      const matched = {
        name: reg.name,
        country: reg.country,
        subdivision: reg.subdivision,
        latitude: lat,
        longitude: lon,
      };
      cache.set(cacheKey, matched);
      return matched;
    }
  }

  // 2. Query BigDataCloud client-side reverse geocoder
  try {
    const url = `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`;
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (res.ok) {
      const data = await res.json();
      const city = data.city || data.locality || data.principalSubdivision;
      const country = data.countryName || (data.localityInfo?.informative?.[0]?.name) || 'Global Sector';
      const subdivision = data.principalSubdivision || '';

      if (city || country) {
        const result = {
          name: city || `${lat.toFixed(4)}°, ${lon.toFixed(4)}°`,
          country: country,
          subdivision: subdivision,
          latitude: lat,
          longitude: lon,
        };
        cache.set(cacheKey, result);
        return result;
      }
    }
  } catch (_) {}

  // 3. Coordinate fallback format
  const latDir = lat >= 0 ? 'N' : 'S';
  const lonDir = lon >= 0 ? 'E' : 'W';
  const fallback = {
    name: `Sector ${Math.abs(lat).toFixed(4)}° ${latDir}, ${Math.abs(lon).toFixed(4)}° ${lonDir}`,
    country: 'Global Planetary Sector',
    subdivision: 'Unincorporated Territory',
    latitude: lat,
    longitude: lon,
  };
  cache.set(cacheKey, fallback);
  return fallback;
}
