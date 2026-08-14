"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { getMe, updateMe, uploadPhoto } from "@/lib/api/profiles";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import type { Profile } from "@fe-el-seka/shared";

export default function CompleteProfilePage() {
  return (
    <Suspense fallback={null}>
      <CompleteProfileForm />
    </Suspense>
  );
}

function CompleteProfileForm() {
  const router = useRouter();
  const t = useTranslations("auth.completeProfile");
  const [accessToken, setAccessToken] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setAccessToken(session.access_token);
      try {
        const me = await getMe(session.access_token);
        setProfile(me);
      } finally {
        setLoading(false);
      }
    });
  }, [router]);

  const handleSubmit = async (
    data: { display_name: string; phone_number?: string },
    photo: File | null,
  ) => {
    await updateMe(accessToken, { display_name: data.display_name, phone_number: data.phone_number });
    if (photo) await uploadPhoto(accessToken, photo);
    // Full reload so the server-rendered "/" gate re-evaluates the now-complete profile.
    window.location.replace("/");
  };

  if (loading || !profile) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
        <Spinner />
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6 py-8">
        <div className="text-center">
          <h1 className="text-h2 text-content-primary">{t("title")}</h1>
          <p className="text-body-sm text-content-muted mt-1">{t("subtitle")}</p>
        </div>
        <ProfileForm
          defaultValues={{
            display_name: profile.display_name,
            profile_photo_url: profile.profile_photo_url,
            phone_number: profile.phone_number,
          }}
          onSubmit={handleSubmit}
          submitLabel={t("submit")}
          showPhone
          photoRequired
        />
      </div>
    </main>
  );
}
