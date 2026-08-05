import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";
import "leaflet/dist/leaflet.css";
import { directionForLocale, isLocale } from "@/lib/i18n/config";

export const metadata: Metadata = {
  title: "Triplyy",
  description: "AI-powered route-sharing and carpooling platform",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const messages = await getMessages();
  const dir = isLocale(locale) ? directionForLocale(locale) : "ltr";

  return (
    <html lang={locale} dir={dir}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
