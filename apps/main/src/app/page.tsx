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
    .select("role, verification_status")
    .eq("id", user.id)
    .maybeSingle();

  if (!profile) redirect("/role-select");

  if (profile.verification_status === "rejected") {
    redirect(profile.role === "driver" ? "/driver/verify-documents" : "/verify-id");
  }

  if (profile.verification_status === "suspended") {
    return <SuspendedScreen />;
  }

  // unverified, pending_review, and verified all get full app access —
  // verification is enforced at gated actions (booking/posting rides), not here.
  if (profile.role === "driver") redirect("/rides");
  if (profile.role === "passenger") redirect("/search");
  // Any other role (e.g. "admin") has no place in the main app.
  // This happens locally when the admin panel session bleeds in via shared cookies.
  redirect("/signout");
}
