import type { Locale } from "@fe-el-seka/shared";

export const locales: Locale[] = ["en", "ar"];

export const defaultLocale: Locale = "ar";

export const localeCookieName = "NEXT_LOCALE";

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "en" || value === "ar";
}

export function directionForLocale(locale: Locale): "ltr" | "rtl" {
  return locale === "ar" ? "rtl" : "ltr";
}
