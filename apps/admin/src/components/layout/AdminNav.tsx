"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/rides", label: "Rides" },
  { href: "/users", label: "Users" },
  { href: "/verification", label: "Verification" },
  { href: "/moderation", label: "Moderation" },
  { href: "/financial", label: "Financial" },
  { href: "/wallet-topup", label: "Wallet Top-Ups" },
  { href: "/sponsored-groups", label: "Sponsored Groups" },
  { href: "/withdrawal-requests", label: "Withdrawal Requests" },
  { href: "/loyalty/queue", label: "Loyalty Queue" },
  { href: "/loyalty/catalog", label: "Loyalty Catalog" },
  { href: "/vehicles", label: "Vehicles" },
];

export function AdminNav() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    const sb = createAdminBrowserClient();
    await sb.auth.signOut();
    window.location.replace("/login");
  }

  return (
    <header className="border-b bg-white sticky top-0 z-10">
      <div className="flex items-center justify-between px-4">
        <nav className="flex items-center gap-1 overflow-x-auto">
          <button
            onClick={() => router.back()}
            aria-label="Go back"
            title="Go back"
            className="p-2 mr-1 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded"
          >
            ←
          </button>
          {LINKS.map((link) => {
            const isActive =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  isActive
                    ? "border-gray-900 text-gray-900"
                    : "border-transparent text-gray-500 hover:text-gray-900"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={handleSignOut}
          className="text-sm text-gray-500 hover:text-gray-900 whitespace-nowrap"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
