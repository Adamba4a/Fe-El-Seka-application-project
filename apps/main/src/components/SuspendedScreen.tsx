"use client";

import { useTranslations } from "next-intl";

export function SuspendedScreen() {
  const t = useTranslations("home");
  const tc = useTranslations("common");

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm text-center space-y-4">
        <h1 className="text-h2 text-content-primary">{tc("appName")}</h1>
        <p className="text-body-sm text-content-destructive">{t("suspendedMessage")}</p>
        <a
          href="/signout"
          className="inline-block py-3 px-4 border border-border-default rounded-xl text-body-sm text-content-secondary font-medium hover:bg-surface-bg transition-colors"
        >
          {t("signOut")}
        </a>
      </div>
    </main>
  );
}
