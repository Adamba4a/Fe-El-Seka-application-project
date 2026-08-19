import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { PendingApprovalWait } from "@/components/PendingApprovalWait";
import { SuspendedScreen } from "@/components/SuspendedScreen";

export const dynamic = "force-dynamic";

export default async function Home() {
  const supabase = createClient();
  const tc = await getTranslations("common");

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("role, verification_status")
    .eq("id", user.id)
    .maybeSingle();

  if (!profile) redirect("/role-select");

  if (profile.verification_status === "unverified") {
    redirect("/profile");
  }

  if (profile.verification_status === "rejected") {
    redirect(profile.role === "driver" ? "/driver/verify-documents" : "/verify-id");
  }

  if (profile.verification_status === "suspended") {
    return <SuspendedScreen />;
  }

  if (profile.verification_status === "verified") {
    if (profile.role === "driver") redirect("/rides");
    if (profile.role === "passenger") redirect("/search");
    // Any other role (e.g. "admin") has no place in the main app.
    // This happens locally when the admin panel session bleeds in via shared cookies.
    redirect("/signout");
  }

  // pending_review — show a waiting screen that auto-refreshes
  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm text-center space-y-4">
        <h1 className="text-h2 text-content-primary">Triplyy</h1>
        <PendingApprovalWait />
      </div>
    </main>
  );
}
