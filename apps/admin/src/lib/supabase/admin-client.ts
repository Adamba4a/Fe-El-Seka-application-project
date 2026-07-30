import { createClient } from "@supabase/supabase-js";
import { env } from "../env";

// Service-role client — used server-side only for signed URL generation and admin actions.
// global.fetch opts out of Next.js's static fetch cache so counts are always live.
export function createAdminClient() {
  return createClient(env.supabaseUrl, env.serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
    global: {
      fetch: (url: RequestInfo | URL, options: RequestInit = {}) =>
        fetch(url, { ...options, cache: "no-store" }),
    },
  });
}
