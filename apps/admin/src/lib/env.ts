const requiredEnvVars = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "NEXT_PUBLIC_API_URL",
  "SUPABASE_SERVICE_ROLE_KEY",
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
  apiUrl: process.env.NEXT_PUBLIC_API_URL!,
  serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY!,
} as const;
