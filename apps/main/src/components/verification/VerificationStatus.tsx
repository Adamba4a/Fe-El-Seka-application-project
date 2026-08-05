import Link from "next/link";
import { useTranslations } from "next-intl";
import type { VerificationStatus, Role } from "@fe-el-seka/shared";

interface Props {
  status: VerificationStatus;
  role?: Role | null;
}

export function VerificationStatusScreen({ status, role }: Props) {
  const t = useTranslations("onboarding.verificationStatus");
  const s = status.verification_status;

  if (s === "pending_review") {
    return (
      <div className="text-center space-y-4 py-8">
        <div className="w-16 h-16 mx-auto bg-status-in-progress-bg rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-status-in-progress" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="text-h2 text-content-primary">{t("pendingTitle")}</h2>
        <p className="text-body-sm text-content-secondary">
          {t("pendingBody")}
        </p>
        {status.attempt_number && (
          <p className="text-caption text-content-muted">{t("attemptOf", { number: status.attempt_number })}</p>
        )}
      </div>
    );
  }

  if (s === "verified") {
    const href = role === "driver" ? "/rides" : "/search";
    const label = role === "driver" ? t("goToMyRides") : t("findARide");
    return (
      <div className="text-center space-y-4 py-8">
        <div className="w-16 h-16 mx-auto bg-status-completed-bg rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-status-completed" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-h2 text-content-primary">{t("verifiedTitle")}</h2>
        <p className="text-body-sm text-content-secondary">{t("verifiedBody")}</p>
        <Link
          href={href}
          className="block w-full py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium text-center transition-colors"
        >
          {label}
        </Link>
      </div>
    );
  }

  if (s === "rejected") {
    const resubmitHref = role === "driver" ? "/driver/verify-documents" : "/verify-id";
    return (
      <div className="text-center space-y-4 py-8">
        <div className="w-16 h-16 mx-auto bg-status-cancelled-bg rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-status-cancelled" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h2 className="text-h2 text-content-primary">{t("rejectedTitle")}</h2>
        {status.rejection_reason && (
          <div className="bg-status-cancelled-bg border border-status-cancelled rounded-xl px-4 py-3 text-left">
            <p className="text-caption text-content-destructive uppercase tracking-wide mb-1">{t("reasonLabel")}</p>
            <p className="text-body-sm text-content-secondary">{status.rejection_reason}</p>
          </div>
        )}
        <Link
          href={resubmitHref}
          className="block w-full py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium text-center transition-colors"
        >
          {t("resubmit")}
        </Link>
        {status.attempt_number && (
          <p className="text-caption text-content-muted">{t("attemptOf", { number: status.attempt_number })}</p>
        )}
      </div>
    );
  }

  return null;
}
