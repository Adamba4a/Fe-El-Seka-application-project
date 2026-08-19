import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";

export const dynamic = "force-dynamic";

export default async function DriverLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile, error } = await supabase
    .from("profiles")
    .select("role, display_name")
    .eq("id", user.id)
    .single();

  // Only redirect if we got a definitive answer that this user is not a driver.
  // A null profile caused by a transient DB error should not bounce the driver out.
  if (!error && profile && profile.role !== "driver") redirect("/");

  // "New User" is the placeholder set at role-select, before the user has
  // submitted their real name/phone/date of birth — signup isn't complete yet.
  if (profile?.display_name === "New User") redirect("/profile");

  return <AppShell variant="driver">{children}</AppShell>;
}
