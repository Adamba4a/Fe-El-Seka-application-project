import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";

export const dynamic = "force-dynamic";

export default async function PassengerLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("display_name, org_verified_at")
    .eq("id", user.id)
    .maybeSingle();

  // "New User" is the placeholder set at role-select, before the user has
  // submitted their real name/phone/date of birth — signup isn't complete yet.
  if (profile?.display_name === "New User") redirect("/profile");

  // Org-email access gate (Spec 025): catches direct navigation to any
  // already-mounted passenger route, not just the initial landing route.
  if (!profile?.org_verified_at) redirect("/verify-org-email");

  return <AppShell variant="passenger">{children}</AppShell>;
}
