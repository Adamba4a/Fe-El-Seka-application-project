"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { OtpInput } from "@/components/auth/OtpInput";
import { requestDomainVerification, confirmDomainVerification } from "@/lib/api/groups";
import type { DomainGroupType, DomainVerificationConfirmResponse } from "@fe-el-seka/shared";

const inputClass =
  "w-full border border-border-default rounded-xl px-3 py-2 text-body-sm outline-none focus:border-border-focus transition-colors";

interface DomainVerifyFormProps {
  token: string;
  requestedGroupType: DomainGroupType;
  onSuccess: (result: DomainVerificationConfirmResponse) => void;
}

export function DomainVerifyForm({ token, requestedGroupType, onSuccess }: DomainVerifyFormProps) {
  const t = useTranslations("groups.domainVerify");
  const [step, setStep] = useState<"email" | "otp">("email");
  const [email, setEmail] = useState("");
  const [verificationId, setVerificationId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<Date | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const mapRequestError = (e: { error?: string; message?: string }) => {
    switch (e?.error) {
      case "invalid_email":
        return t("errors.invalidEmail");
      case "blocklisted_domain":
        return t("errors.blocklistedDomain");
      case "otp_rate_limited":
        return t("errors.otpRateLimited");
      case "otp_send_failed":
        return t("errors.sendFailed");
      default:
        return e?.message ?? t("errors.sendFailed");
    }
  };

  const mapConfirmError = (e: { error?: string; message?: string }) => {
    switch (e?.error) {
      case "otp_invalid":
        return t("errors.invalidCode");
      case "otp_expired":
        return t("errors.expired");
      case "otp_already_used":
        return t("errors.alreadyUsed");
      case "domain_group_archived":
        return t("errors.domainArchived");
      case "domain_registration_rate_limited":
        return t("errors.registrationRateLimited");
      default:
        return e?.message ?? t("errors.invalidCode");
    }
  };

  const handleRequestCode = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const res = await requestDomainVerification(token, {
        email: email.trim(),
        requested_group_type: requestedGroupType,
      });
      setVerificationId(res.verification_id);
      setExpiresAt(new Date(Date.now() + res.expires_in_seconds * 1000));
      setStep("otp");
    } catch (err) {
      setError(mapRequestError(err as { error?: string; message?: string }));
    } finally {
      setLoading(false);
    }
  };

  const handleOtpComplete = async (code: string) => {
    if (loading || !verificationId) return;
    setLoading(true);
    setError("");
    try {
      const result = await confirmDomainVerification(token, { verification_id: verificationId, code });
      onSuccess(result);
    } catch (err) {
      setError(mapConfirmError(err as { error?: string; message?: string }));
    } finally {
      setLoading(false);
    }
  };

  if (step === "otp") {
    return (
      <div className="space-y-4">
        <div className="text-center">
          <h3 className="text-label text-content-secondary">{t("otpTitle")}</h3>
          <p className="text-body-sm text-content-muted mt-1">
            {t.rich("otpSubtitle", {
              email,
              strong: (chunks) => <strong className="text-content-secondary">{chunks}</strong>,
            })}
          </p>
        </div>
        <OtpInput
          onComplete={handleOtpComplete}
          disabled={loading}
          error={error}
          expiresAt={expiresAt}
          onResend={handleRequestCode}
        />
      </div>
    );
  }

  return (
    <form onSubmit={handleRequestCode} className="space-y-3">
      <div className="space-y-1">
        <label className="block text-label text-content-secondary">{t("emailLabel")}</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t("emailPlaceholder")}
          required
          className={inputClass}
        />
        <p className="text-caption text-content-muted">{t("domainVerifiedHint")}</p>
      </div>

      {error && <p className="text-body-sm text-content-destructive">{error}</p>}

      <button
        type="submit"
        disabled={loading || !email.trim()}
        className="w-full bg-dash-primary hover:opacity-90 disabled:opacity-50 text-content-inverse rounded-xl py-3 font-medium transition-opacity"
      >
        {loading ? t("sending") : t("sendCode")}
      </button>
    </form>
  );
}
