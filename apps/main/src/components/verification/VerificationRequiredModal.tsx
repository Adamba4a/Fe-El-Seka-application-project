"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { BottomSheet } from "@/components/ui/BottomSheet";
import type { Role } from "@fe-el-seka/shared";

interface VerificationRequiredModalProps {
  isOpen: boolean;
  onClose: () => void;
  role: Role;
}

export function VerificationRequiredModal({ isOpen, onClose, role }: VerificationRequiredModalProps) {
  const t = useTranslations("onboarding.verificationRequired");
  const verifyHref = role === "driver" ? "/driver/verify-documents" : "/verify-id";

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose}>
      <div className="space-y-4 text-center pt-1">
        <h2 className="text-h3 text-content-primary">{t("title")}</h2>
        <p className="text-body-sm text-content-muted">{t("body")}</p>
        <Link
          href={verifyHref}
          className="block w-full text-center py-3 px-4 bg-dash-primary hover:opacity-90 text-content-inverse rounded-xl font-medium transition-opacity"
        >
          {t("cta")}
        </Link>
        <button
          type="button"
          onClick={onClose}
          className="text-body-sm text-content-muted underline"
        >
          {t("dismiss")}
        </button>
      </div>
    </BottomSheet>
  );
}
