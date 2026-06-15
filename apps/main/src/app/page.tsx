import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function Home() {
  const supabase = createClient();

  const { data: { session } } = await supabase.auth.getSession();
  if (!session) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("role, verification_status")
    .eq("id", session.user.id)
    .maybeSingle();

  if (!profile) redirect("/role-select");

  // Send users without approved docs back to the upload flow
  if (profile.verification_status === "unverified" || profile.verification_status === "rejected") {
    redirect(
      profile.role === "driver"
        ? "/driver/verify-documents"
        : "/verify-id"
    );
  }

  const messages: Record<string, string> = {
    pending_review: "Your documents are under review. We'll notify you once a decision is made.",
    verified: "Your identity is verified! The full app is coming soon.",
    suspended: "Your account has been suspended. Please contact support.",
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm text-center space-y-4">
        <h1 className="text-2xl font-bold">Fe El Seka</h1>
        <p className="text-gray-600">
          {messages[profile.verification_status] ?? "Welcome to Fe El Seka."}
        </p>
      </div>
    </main>
  );
}
