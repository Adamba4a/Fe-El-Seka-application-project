import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { SuspendedScreen } from "@/components/SuspendedScreen";

export const dynamic = "force-dynamic";

export default async function Home() {
  const supabase = createClient();

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("role, display_name, verification_status, org_verified_at")
    .eq("id", user.id)
    .maybeSingle();

  if (!profile) redirect("/role-select");

  // "New User" is the placeholder set at role-select, before the user has
  // submitted their real name/phone/date of birth — signup isn't complete yet.
  if (profile.display_name === "New User") redirect("/profile");

  if (profile.verification_status === "suspended") {
    return <SuspendedScreen />;
  }

  // Org-email access gate (Spec 025): every account, new or pre-existing,
  // must verify a company/university email before reaching the main app —
  // checked after suspension (FR-012) but before role-based routing.
  if (!profile.org_verified_at) redirect("/verify-org-email");

  // National ID verification (Spec 021) no longer gates anything: org-email
  // verification (Spec 025) is the platform's sole trust-floor requirement,
  // so every verification_status value gets full app access here.
  if (profile.role === "driver") redirect("/rides");
  if (profile.role === "passenger") redirect("/dashboard");
  // Any other role (e.g. "admin") has no place in the main app.
  // This happens locally when the admin panel session bleeds in via shared cookies.
  redirect("/signout");
}
