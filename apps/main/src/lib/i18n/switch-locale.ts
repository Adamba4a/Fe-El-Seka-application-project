"use client";

import type { Locale } from "@fe-el-seka/shared";
import { updateMe } from "@/lib/api/profiles";
import { localeCookieName } from "./config";

// Shared by every language-toggle entry point (Settings, TopBar, login screen)
// so the two code paths described in tasks.md T028 stay in exactly one place:
// authenticated users persist the choice to `profiles.language_preference`
// (middleware.ts resolves that on the next request and rewrites the cookie);
// unauthenticated visitors have no profile row, so the cookie is the only
// place to remember the choice.
export async function switchLocale(locale: Locale, accessToken: string | null): Promise<void> {
  if (accessToken) {
    await updateMe(accessToken, { language_preference: locale });
  } else {
    document.cookie = `${localeCookieName}=${locale}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
  }
}
