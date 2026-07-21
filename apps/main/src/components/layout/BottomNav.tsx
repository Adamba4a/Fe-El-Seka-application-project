"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

function DashboardIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z" />
    </svg>
  );
}

function CarIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M5 17h14M5 17a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm14 0a2 2 0 1 0 4 0 2 2 0 0 0-4 0ZM3 17V11l2-5h14l2 5v6M3 11h18" />
    </svg>
  );
}

function WalletIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M16 12h3v3h-3a1.5 1.5 0 0 1 0-3Z" />
    </svg>
  );
}

function ProfileIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
    </svg>
  );
}

function TripsIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" />
    </svg>
  );
}

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
}

const DRIVER_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: <DashboardIcon /> },
  { href: "/rides", label: "My Rides", icon: <CarIcon /> },
  { href: "/wallet", label: "Earnings", icon: <WalletIcon /> },
  { href: "/settings/profile", label: "Profile", icon: <ProfileIcon /> },
];

const PASSENGER_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: <DashboardIcon /> },
  { href: "/search", label: "Find a Ride", icon: <SearchIcon /> },
  { href: "/bookings", label: "My Trips", icon: <TripsIcon /> },
  { href: "/settings/profile", label: "Profile", icon: <ProfileIcon /> },
];

export function BottomNav({ variant }: { variant: "driver" | "passenger" }) {
  const pathname = usePathname();
  const items = variant === "driver" ? DRIVER_ITEMS : PASSENGER_ITEMS;

  return (
    <nav className="fixed bottom-0 inset-x-0 bg-dash-surface border-t border-dash-border z-10">
      <div className="max-w-2xl mx-auto flex">
        {items.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex-1 flex flex-col items-center gap-1 py-2.5 text-xs font-medium transition-colors ${
                active ? "text-dash-primary" : "text-dash-text-muted"
              }`}
            >
              {item.icon}
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
