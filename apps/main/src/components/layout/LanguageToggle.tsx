"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useSession } from "@/lib/auth/hooks";
import { switchLocale } from "@/lib/i18n/switch-locale";
import type { Locale } from "@fe-el-seka/shared";

// Always-accessible language switcher (T027). Reads the active session itself
// so callers don't need to thread an access token through every layout —
// switchLocale() persists to the profile when signed in, or the NEXT_LOCALE
// cookie otherwise (see switch-locale.ts).
export function LanguageToggle({ className }: { className?: string }) {
  const t = useTranslations("nav");
  const currentLocale = useLocale() as Locale;
  const session = useSession();
  const router = useRouter();
  const [saving, setSaving] = useState(false);

  const nextLocale: Locale = currentLocale === "ar" ? "en" : "ar";

  const handleToggle = async () => {
    if (saving) return;
    setSaving(true);
    try {
      await switchLocale(nextLocale, session?.access_token ?? null);
      router.refresh();
    } finally {
      setSaving(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={saving}
      aria-label={t(nextLocale === "ar" ? "switchToArabic" : "switchToEnglish")}
      className={className ?? "text-body-sm font-semibold text-dash-navy disabled:opacity-50"}
    >
      {nextLocale === "ar" ? "AR" : "EN"}
    </button>
  );
}
