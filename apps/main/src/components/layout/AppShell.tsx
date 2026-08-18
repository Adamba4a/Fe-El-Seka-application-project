"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/lib/auth/hooks";
import { getMe } from "@/lib/api/profiles";
import { LanguagePromptModal } from "@/app/(app)/settings/profile/LanguagePromptModal";
import { onAccountSuspended } from "@/lib/auth/suspension-watcher";
import { SuspendedScreen } from "@/components/SuspendedScreen";
import type { Profile } from "@fe-el-seka/shared";
import { TopBar } from "./TopBar";
import { BottomNav } from "./BottomNav";

interface AppShellProps {
  variant: "driver" | "passenger";
  children: React.ReactNode;
}

export function AppShell({ variant, children }: AppShellProps) {
  const session = useSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [suspended, setSuspended] = useState(false);
  const t = useTranslations("nav");

  useEffect(() => onAccountSuspended(() => setSuspended(true)), []);

  useEffect(() => {
    if (!session?.access_token) return;
    getMe(session.access_token)
      .then(setProfile)
      .catch(() => {});
  }, [session]);

  const userName =
    profile?.display_name ?? (variant === "driver" ? t("defaultDriverName") : t("defaultPassengerName"));

  if (suspended) return <SuspendedScreen />;

  return (
    <div className="min-h-screen bg-dash-bg">
      {session?.access_token && profile && profile.language_preference == null && (
        <LanguagePromptModal
          accessToken={session.access_token}
          onSelected={(locale) =>
            setProfile((prev) => (prev ? { ...prev, language_preference: locale } : prev))
          }
        />
      )}
      <TopBar variant={variant} userName={userName} avatarUrl={profile?.profile_photo_url} />
      <main className="max-w-2xl mx-auto px-4 pb-24">{children}</main>
      <BottomNav variant={variant} />
    </div>
  );
}
