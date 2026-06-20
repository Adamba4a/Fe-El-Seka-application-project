"use client";

import { useEffect } from "react";
import { createClient } from "@/lib/supabase/client";

export function PendingApprovalWait() {
  useEffect(() => {
    const supabase = createClient();

    const check = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data: profile } = await supabase
        .from("profiles")
        .select("role, verification_status")
        .eq("id", user.id)
        .maybeSingle();
      if (profile?.verification_status === "verified") {
        // (driver) is a route group — real URL is /rides, not /driver/rides.
        // Non-drivers go to settings until a passenger dashboard exists.
        window.location.href = profile.role === "driver" ? "/rides" : "/settings/profile";
      }
    };

    // Check immediately on mount, then every 10 seconds
    check();
    const interval = setInterval(check, 10_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <div className="w-10 h-10 border-4 border-brand-primary border-t-transparent rounded-full animate-spin" />
      </div>
      <p className="text-body-sm text-content-secondary font-medium">Your documents are under review.</p>
      <p className="text-body-sm text-content-muted">
        This page will update automatically once a decision is made.
      </p>
    </div>
  );
}
