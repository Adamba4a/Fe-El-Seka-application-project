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
    .select("role, display_name, verification_status")
    .eq("id", user.id)
    .maybeSingle();

  // Mirrors app/page.tsx's gating — an authenticated user can land here
  // directly (back/forward nav, a bookmark, a stale link) before finishing
  // signup, and this page must not skip straight to full app access.
  if (!profile) redirect("/role-select");
  if (profile.display_name === "New User") redirect("/profile");

  const isDriver = profile.role === "driver";

  // Rejected users are sent to resubmit, mirroring app/page.tsx's redirect —
  // unverified, pending_review, and verified all get full dashboard access;
  // verification is enforced at gated actions, not here.
  if (profile.verification_status === "rejected") {
    redirect(isDriver ? "/driver/verify-documents" : "/verify-id");
  }

  return (
    <AppShell variant={isDriver ? "driver" : "passenger"}>
      {isDriver ? <DriverDashboard /> : <PassengerDashboard />}
    </AppShell>
  );
}
