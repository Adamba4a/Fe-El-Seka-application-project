import { env } from "./env";

// OpenStreetMap's own tile server (tile.openstreetmap.org) explicitly
// disallows production app traffic and throttles/blocks it without notice —
// that's what caused tiles to silently stop rendering in prod. MapTiler's
// free tier (100k tile loads/month) is a drop-in raster replacement; local
// dev without a key falls back to the raw OSM tiles since that volume is low.
export const TILE_URL = env.mapTilerKey
  ? `https://api.maptiler.com/maps/bright-v2/{z}/{x}/{y}.png?key=${env.mapTilerKey}`
  : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

export const TILE_ATTRIBUTION = env.mapTilerKey
  ? '<a href="https://www.maptiler.com/copyright/" target="_blank">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">© OpenStreetMap contributors</a>'
  : '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

export const TILE_MAX_ZOOM = 19;
