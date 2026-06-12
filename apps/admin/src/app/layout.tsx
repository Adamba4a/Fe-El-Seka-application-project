import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fe El Seka Admin",
  description: "Fe El Seka platform administration",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
