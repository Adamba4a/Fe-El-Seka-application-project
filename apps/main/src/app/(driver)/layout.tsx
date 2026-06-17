import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export default async function DriverLayout({ children }: { children: React.ReactNode }) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  if (!profile || profile.role !== "driver") redirect("/");

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <span className="font-semibold text-gray-900">Fe El Seka</span>
          <nav className="flex gap-4 text-sm">
            <a href="/driver/rides" className="text-blue-600 font-medium">My Rides</a>
            <a href="/app/settings/profile" className="text-gray-500">Profile</a>
          </nav>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
