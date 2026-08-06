"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { switchLocale } from "@/lib/i18n/switch-locale";
import type { Locale } from "@fe-el-seka/shared";

// One-time rollout prompt (FR-013 / T030) for authenticated users whose
// language_preference is still NULL. Non-blocking by design (research.md R5):
// it's a plain overlay, not a route guard like /onboarding/verify-id, so the
// app underneath remains navigable — it only disappears once a choice is made.
export function LanguagePromptModal({ accessToken }: { accessToken: string }) {
  const t = useTranslations("languagePrompt");
  const tl = useTranslations("settings.profile.editor.language");
  const router = useRouter();
  const [saving, setSaving] = useState(false);

  const handleSelect = async (locale: Locale) => {
    if (saving) return;
    setSaving(true);
    try {
      await switchLocale(locale, accessToken);
      router.refresh();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-6">
      <div className="w-full max-w-xs space-y-4 rounded-2xl bg-surface-card p-6 shadow-lg">
        <div className="text-center space-y-1">
          <h2 className="text-h3 text-content-primary">{t("heading")}</h2>
          <p className="text-body-sm text-content-muted">{t("subheading")}</p>
        </div>
        <div className="flex gap-2">
          {(["en", "ar"] as const).map((locale) => (
            <button
              key={locale}
              type="button"
              onClick={() => handleSelect(locale)}
              disabled={saving}
              className="flex-1 rounded-xl border border-border-default py-3 text-body-sm font-medium text-content-secondary transition-colors hover:bg-surface-bg disabled:opacity-50"
            >
              {tl(locale === "en" ? "english" : "arabic")}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
