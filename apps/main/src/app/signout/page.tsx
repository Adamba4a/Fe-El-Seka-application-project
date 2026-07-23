"use client";

import { useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { SESSION_STARTED_COOKIE } from "@/lib/auth/session-age";

// Signs the current user out and sends them to /login.
// Used when an unexpected session is detected (e.g. admin session bleeding
// from the admin panel into the main app on localhost).
export default function SignOutPage() {
  useEffect(() => {
    createClient()
      .auth.signOut()
      .finally(() => {
        // Clear the 24h-cap clock so the next login starts its own window
        // instead of inheriting this session's (possibly near-expired) one.
        document.cookie = `${SESSION_STARTED_COOKIE}=; path=/; max-age=0`;
        window.location.replace("/login");
      });
  }, []);

  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-body-sm text-content-muted">Signing out…</p>
    </main>
  );
}
