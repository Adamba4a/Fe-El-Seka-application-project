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

  const { data: profile, error } = await supabase
    .from("profiles")
    .select("role, verification_status")
    .eq("id", user.id)
    .single();

  const isDriver = !error && profile?.role === "driver";

  // Rejected users are sent to resubmit, mirroring app/page.tsx's redirect —
  // unverified, pending_review, and verified all get full dashboard access;
  // verification is enforced at gated actions, not here.
  if (!isDriver && !error && profile && profile.verification_status === "rejected") {
    redirect("/verify-id");
  }

  return (
    <AppShell variant={isDriver ? "driver" : "passenger"}>
      {isDriver ? <DriverDashboard /> : <PassengerDashboard />}
    </AppShell>
  );
}
