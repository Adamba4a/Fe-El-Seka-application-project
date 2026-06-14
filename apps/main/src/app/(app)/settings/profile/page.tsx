"use client";

import { useEffect, useState } from "react";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { getMe, updateMe, uploadPhoto } from "@/lib/api/profiles";
import { createClient } from "@/lib/supabase/client";
import type { Profile } from "@fe-el-seka/shared";

export default function SettingsProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const load = async () => {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const p = await getMe(session.access_token);
      setProfile(p);
    };
    load();
  }, []);

  const handleSubmit = async ({ display_name }: { display_name: string }, photo: File | null) => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    const updated = await updateMe(session.access_token, { display_name });
    if (photo) await uploadPhoto(session.access_token, photo);
    setProfile(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  if (!profile) return <div className="p-8 text-center text-gray-400">Loading…</div>;

  return (
    <main className="max-w-sm mx-auto p-6 space-y-6">
      <h1 className="text-xl font-bold">Edit Profile</h1>
      {saved && <p className="text-green-600 text-sm">Profile saved!</p>}
      <ProfileForm
        defaultValues={{ display_name: profile.display_name, profile_photo_url: profile.profile_photo_url }}
        onSubmit={handleSubmit}
        submitLabel="Save Changes"
      />
    </main>
  );
}
