import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AppShell } from "@/components/layout/AppShell";

export const dynamic = "force-dynamic";

export default async function AppGroupLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile, error } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  const isDriver = !error && profile?.role === "driver";

  return <AppShell variant={isDriver ? "driver" : "passenger"}>{children}</AppShell>;
}
