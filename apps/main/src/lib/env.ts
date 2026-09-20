const requiredEnvVars = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "NEXT_PUBLIC_API_URL",
  "NEXT_PUBLIC_GOOGLE_MAPS_API_KEY",
] as const;

// Only validate server-side. In the browser, Next.js inlines NEXT_PUBLIC_* via
// webpack DefinePlugin using static property access only — computed bracket notation
// (process.env[key]) always returns undefined in the browser even when the var is set.
if (typeof window === "undefined") {
  for (const key of requiredEnvVars) {
    if (!process.env[key]) {
      throw new Error(`Missing required environment variable: ${key}`);
    }
  }
}

export const env = {
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL!,
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  // Browser requests go through the same-origin /api proxy.  Bunny can be
  // configured with the Next.js container as its origin, in which case a
  // browser request to the public API URL never reaches nginx/FastAPI.
  // Keeping the request same-origin also removes a needless CORS dependency.
  apiUrl: typeof window === "undefined" ? process.env.NEXT_PUBLIC_API_URL! : "",
  // Server-side fetch uses the Docker-internal URL so it can reach the api
  // container directly without going through nginx. Falls back to the public
  // URL in local dev where BACKEND_INTERNAL_URL is not set.
  serverApiUrl: process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL!,
  googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!,
} as const;
