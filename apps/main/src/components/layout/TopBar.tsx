"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { LanguageToggle } from "./LanguageToggle";

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function Avatar({
  url,
  name,
  size = "md",
}: {
  url?: string | null;
  name: string;
  size?: "sm" | "md";
}) {
  const dim = size === "sm" ? "w-9 h-9" : "w-11 h-11";
  const [broken, setBroken] = useState(false);
  if (url && !broken) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={name}
        className={`${dim} rounded-full object-cover`}
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div
      className={`${dim} rounded-full bg-dash-primary text-white flex items-center justify-center text-sm font-semibold`}
    >
      {initials(name) || "?"}
    </div>
  );
}

function GearIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 0 0 1.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 0 0-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 0 0-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 0 0-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 0 0-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 0 0 1.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065Z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

interface TopBarProps {
  variant: "driver" | "passenger";
  userName: string;
  avatarUrl?: string | null;
}

export function TopBar({ variant, userName, avatarUrl }: TopBarProps) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  return (
    <header className="bg-dash-bg sticky top-0 z-10 px-4 pt-4 pb-3">
      <div className="max-w-2xl mx-auto flex items-center justify-between">
        {variant === "driver" ? (
          <div className="flex items-center gap-3">
            <Avatar url={avatarUrl} name={userName} />
            <div>
              <p className="text-dash-navy font-semibold leading-tight">{userName}</p>
              <p className="text-[11px] font-semibold tracking-wide text-dash-primary flex items-center gap-1 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-dash-primary inline-block" />
                {t("verifiedDriver")}
              </p>
            </div>
          </div>
        ) : (
          <span className="text-2xl font-bold text-dash-navy">{tc("appName")}</span>
        )}

        <div className="flex items-center gap-4">
          <LanguageToggle />
          {variant === "driver" ? (
            <Link href="/settings/profile" aria-label={t("settingsAriaLabel")} className="text-dash-navy">
              <GearIcon />
            </Link>
          ) : (
            <Link href="/settings/profile" aria-label={t("profileAriaLabel")}>
              <Avatar url={avatarUrl} name={userName} size="sm" />
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
