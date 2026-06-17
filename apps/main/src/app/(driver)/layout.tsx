import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function DriverLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile, error } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  // Only redirect if we got a definitive answer that this user is not a driver.
  // A null profile caused by a transient DB error should not bounce the driver out.
  if (!error && profile && profile.role !== "driver") redirect("/");

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <span className="font-semibold text-gray-900">Fe El Seka</span>
          <nav className="flex gap-4 text-sm">
            <a href="/rides" className="text-blue-600 font-medium">My Rides</a>
            <a href="/settings/profile" className="text-gray-500">Profile</a>
          </nav>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
