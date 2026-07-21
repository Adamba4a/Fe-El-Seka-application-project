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

  // Passengers must be verified before seeing the dashboard, mirroring the
  // (passenger) route group's guard. Drivers have no equivalent check here,
  // mirroring the (driver) route group's guard.
  if (!isDriver && !error && profile && profile.verification_status !== "verified") {
    redirect("/onboarding/verify-id");
  }

  return (
    <AppShell variant={isDriver ? "driver" : "passenger"}>
      {isDriver ? <DriverDashboard /> : <PassengerDashboard />}
    </AppShell>
  );
}
