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
      <main className="max-w-2xl mx-auto px-4 py-6 pb-24">{children}</main>

      {/* Bottom navigation bar */}
      <nav className="fixed bottom-0 inset-x-0 bg-surface-card border-t border-border-default z-10">
        <div className="max-w-2xl mx-auto flex">
          <a
            href="/search"
            className="flex-1 flex flex-col items-center gap-1 py-2 text-xs font-medium text-brand-primary"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
            </svg>
            Search
          </a>
          <a
            href="/bookings"
            className="flex-1 flex flex-col items-center gap-1 py-2 text-xs font-medium text-content-muted"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" />
            </svg>
            My Bookings
          </a>
        </div>
      </nav>
    </div>
  );
}
