import type { Metadata } from "next";
import "./globals.css";
import "leaflet/dist/leaflet.css";

export const metadata: Metadata = {
  title: "Fe El Seka",
  description: "AI-powered route-sharing and carpooling platform",
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
