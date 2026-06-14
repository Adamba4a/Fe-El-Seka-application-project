"use client";

import { useRouter } from "next/navigation";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { updateMe, uploadPhoto } from "@/lib/api/profiles";
import { createClient } from "@/lib/supabase/client";
import { useRole } from "@/lib/auth/hooks";

export default function ProfileOnboardingPage() {
  const router = useRouter();
  const role = useRole();

  const handleSubmit = async ({ display_name }: { display_name: string }, photo: File | null) => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/login"); return; }

    await updateMe(session.access_token, { display_name });
    if (photo) await uploadPhoto(session.access_token, photo);

    if (role === "driver") {
      router.push("/driver/verify-documents");
    } else {
      router.push("/verify-id");
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Set up your profile</h1>
          <p className="text-gray-500 text-sm mt-1">Add your name and an optional photo</p>
        </div>
        <ProfileForm onSubmit={handleSubmit} submitLabel="Next" />
      </div>
    </main>
  );
}
