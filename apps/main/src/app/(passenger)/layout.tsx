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
    .select("display_name")
    .eq("id", user.id)
    .maybeSingle();

  // "New User" is the placeholder set at role-select, before the user has
  // submitted their real name/phone/date of birth — signup isn't complete yet.
  if (profile?.display_name === "New User") redirect("/profile");

  return <AppShell variant="passenger">{children}</AppShell>;
}
