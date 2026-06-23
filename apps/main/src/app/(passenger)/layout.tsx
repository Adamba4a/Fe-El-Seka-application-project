import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

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
  if (!error && profile && profile.verification_status !== "approved") {
    redirect("/onboarding/verify-id");
  }

  return (
    <div className="min-h-screen bg-surface-bg">
      <header className="bg-surface-card border-b border-border-default sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <span className="font-semibold text-content-primary">Fe El Seka</span>
          <nav className="flex gap-4 text-sm">
            <a href="/search" className="text-brand-primary font-medium">Search</a>
            <a href="/bookings" className="text-content-muted">My Bookings</a>
            <a href="/settings/profile" className="text-content-muted">Profile</a>
          </nav>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
