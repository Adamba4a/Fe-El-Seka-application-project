import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";
import { defaultLocale, isLocale, localeCookieName } from "./config";
import { getMessages as loadMessages } from "./messages-loader";

// Locale is resolved once per request by middleware.ts (profiles.language_preference
// → NEXT_LOCALE cookie → default), which writes the result back into the
// NEXT_LOCALE cookie before this config runs. This avoids a second profiles
// query on every request.
export default getRequestConfig(async () => {
  const cookieLocale = cookies().get(localeCookieName)?.value;
  const locale = isLocale(cookieLocale) ? cookieLocale : defaultLocale;
  const messages = await loadMessages(locale);
  return { locale, messages };
});
