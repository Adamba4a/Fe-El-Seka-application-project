"use client";

import { useEffect } from "react";
import { createClient } from "@/lib/supabase/client";

// Signs the current user out and sends them to /login.
// Used when an unexpected session is detected (e.g. admin session bleeding
// from the admin panel into the main app on localhost).
export default function SignOutPage() {
  useEffect(() => {
    createClient()
      .auth.signOut()
      .finally(() => {
        window.location.replace("/login");
      });
  }, []);

  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-gray-500 text-sm">Signing out…</p>
    </main>
  );
}
