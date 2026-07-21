"use client";

import { useEffect, useState } from "react";
import { useSession } from "@/lib/auth/hooks";
import { getMe } from "@/lib/api/profiles";
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

  useEffect(() => {
    if (!session?.access_token) return;
    getMe(session.access_token)
      .then(setProfile)
      .catch(() => {});
  }, [session]);

  const userName = profile?.display_name ?? (variant === "driver" ? "Driver" : "Passenger");

  return (
    <div className="min-h-screen bg-dash-bg">
      <TopBar variant={variant} userName={userName} avatarUrl={profile?.profile_photo_url} />
      <main className="max-w-2xl mx-auto px-4 pb-24">{children}</main>
      <BottomNav variant={variant} />
    </div>
  );
}
