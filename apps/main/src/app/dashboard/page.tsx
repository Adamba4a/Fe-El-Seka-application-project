import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";
import { DriverDashboard } from "@/components/driver/DriverDashboard";
import { PassengerDashboard } from "@/components/passenger/PassengerDashboard";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("role, display_name, verification_status, org_verified_at")
    .eq("id", user.id)
    .maybeSingle();

  // Mirrors app/page.tsx's gating — an authenticated user can land here
  // directly (back/forward nav, a bookmark, a stale link) before finishing
  // signup, and this page must not skip straight to full app access.
  if (!profile) redirect("/role-select");
  if (profile.display_name === "New User") redirect("/profile");

  // Org-email access gate (Spec 025): catches direct navigation to
  // /dashboard, not just the initial landing route.
  if (!profile.org_verified_at) redirect("/verify-org-email");

  const isDriver = profile.role === "driver";

  // National ID verification (Spec 021) no longer gates anything: org-email
  // verification (Spec 025) is the platform's sole trust-floor requirement,
  // so every verification_status value gets full dashboard access here.

  return (
    <AppShell variant={isDriver ? "driver" : "passenger"}>
      {isDriver ? <DriverDashboard /> : <PassengerDashboard />}
    </AppShell>
  );
}
