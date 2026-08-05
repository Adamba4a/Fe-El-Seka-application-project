"use client";

import { useTranslations } from "next-intl";

export default function ProfileError({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  const t = useTranslations("settings.profile.error");

  return (
    <main className="max-w-sm mx-auto p-6 space-y-4">
      <div className="flex items-center gap-3">
        <a href="/" className="text-content-muted hover:text-content-secondary text-lg leading-none">
          <span className="inline-block rtl:rotate-180">←</span>
        </a>
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
      </div>
      <p className="text-body-sm text-content-destructive">{t("body")}</p>
      <div className="flex gap-3">
        <button
          onClick={reset}
          className="text-body-sm text-brand-primary hover:underline"
        >
          {t("tryAgain")}
        </button>
        <a href="/" className="text-body-sm text-content-muted hover:underline">
          {t("goHome")}
        </a>
      </div>
    </main>
  );
}
