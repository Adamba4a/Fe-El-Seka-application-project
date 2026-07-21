import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";

export const dynamic = "force-dynamic";

export default async function PassengerLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile, error } = await supabase
    .from("profiles")
    .select("verification_status")
    .eq("id", user.id)
    .single();

  // Redirect unverified users; allow transient DB errors through to avoid bounce loops
  if (!error && profile && profile.verification_status !== "verified") {
    redirect("/onboarding/verify-id");
  }

  return <AppShell variant="passenger">{children}</AppShell>;
}
