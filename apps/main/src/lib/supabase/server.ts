import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { env } from "../env";

const serverSupabaseUrl = process.env.SUPABASE_INTERNAL_URL ?? env.supabaseUrl;

export function createClient() {
  const cookieStore = cookies();
  return createServerClient(serverSupabaseUrl, env.supabaseAnonKey, {
    cookieOptions: { name: "sb-fe-el-seka-auth" },
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          );
        } catch {
          // setAll called from a Server Component — cookies are read-only
        }
      },
    },
  });
}
