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
        // Hard redirect — bypasses Next.js router cache entirely
        window.location.href = profile.role === "driver" ? "/driver/rides" : "/";
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
        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
      <p className="text-gray-600 font-medium">Your documents are under review.</p>
      <p className="text-sm text-gray-400">
        This page will update automatically once a decision is made.
      </p>
    </div>
  );
}
