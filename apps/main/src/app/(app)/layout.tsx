import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";

export const dynamic = "force-dynamic";

export default async function AppGroupLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("role, display_name, org_verified_at")
    .eq("id", user.id)
    .maybeSingle();

  // Mirrors app/page.tsx's gating — settings/ratings/users are reachable
  // directly (back/forward nav, a bookmark) before signup is finished, and
  // must not grant app access to an incomplete profile.
  if (!profile) redirect("/role-select");
  if (profile.display_name === "New User") redirect("/profile");

  // Org-email access gate (Spec 025): catches direct navigation to any
  // already-mounted app-shell route, not just the initial landing route.
  if (!profile.org_verified_at) redirect("/verify-org-email");

  const isDriver = profile.role === "driver";

  return <AppShell variant={isDriver ? "driver" : "passenger"}>{children}</AppShell>;
}
