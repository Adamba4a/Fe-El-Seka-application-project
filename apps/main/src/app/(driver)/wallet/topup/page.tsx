"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import {
  getSettings,
  submitRequest,
  VODAFONE_CASH_NUMBER_NOT_CONFIGURED,
  type TopupSettings,
} from "@/lib/api/wallet-topup";
import { DocumentUpload } from "@/components/verification/DocumentUpload";
import { Spinner } from "@/components/ui/Spinner";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

export default function WalletTopupPage() {
  const router = useRouter();
  const t = useTranslations("driver.walletTopup");
  const [settings, setSettings] = useState<TopupSettings | null>(null);
  const [loadError, setLoadError] = useState("");
  const [amount, setAmount] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const load = useCallback(async () => {
    try {
      const token = await getToken();
      const data = await getSettings(token);
      setSettings(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : JSON.stringify(err);
      setLoadError(t("loadFailedPrefix", { message: msg }));
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!screenshot) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      const token = await getToken();
      await submitRequest(token, amount, paymentReference, screenshot);
      setSubmitted(true);
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string; support_email?: string };
      const knownErrors = ["validation_error", "pending_request_exists", "duplicate_payment_reference", "submission_locked"];
      if (e?.error && knownErrors.includes(e.error)) {
        setSubmitError(t(`errors.${e.error}`, { email: e.support_email ?? "" }));
      } else {
        setSubmitError(t("errors.generic"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loadError) return <p className="text-content-destructive text-body-sm p-4">{loadError}</p>;
  if (!settings) return <p className="text-content-muted text-body-sm p-4">{t("loading")}</p>;

  if (settings.is_locked) {
    return (
      <div className="p-4 space-y-4 text-center">
        <h1 className="text-h3 text-content-primary">{t("lockedHeading")}</h1>
        <p className="text-body-sm text-content-secondary">
          {t("lockedBody", { email: settings.support_email ?? "" })}
        </p>
        <button onClick={() => router.push("/wallet")} className="text-body-sm text-brand-primary underline">
          {t("heading")}
        </button>
      </div>
    );
  }

  if (settings.vodafone_cash_number === VODAFONE_CASH_NUMBER_NOT_CONFIGURED) {
    return (
      <div className="p-4 space-y-4 text-center">
        <h1 className="text-h3 text-content-primary">{t("unavailableHeading")}</h1>
        <p className="text-body-sm text-content-secondary">{t("unavailableBody")}</p>
        <button onClick={() => router.push("/wallet")} className="text-body-sm text-brand-primary underline">
          {t("heading")}
        </button>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="p-4 space-y-4 text-center">
        <h1 className="text-h3 text-content-primary">{t("pendingHeading")}</h1>
        <p className="text-body-sm text-content-secondary">{t("pendingBody")}</p>
        <button onClick={() => router.push("/wallet/topup/history")} className="text-body-sm text-brand-primary underline">
          {t("history.heading")}
        </button>
        <button onClick={() => router.push("/wallet")} className="block mx-auto text-body-sm text-content-muted underline">
          {t("heading")}
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-h2 text-content-primary">{t("heading")}</h1>
          <p className="text-body-sm text-content-muted mt-1">{t("instructions")}</p>
        </div>
        <button
          onClick={() => router.push("/wallet/topup/history")}
          className="text-body-sm text-brand-primary font-medium hover:underline whitespace-nowrap"
        >
          {t("history.heading")}
        </button>
      </div>

      <div className="bg-surface-card rounded-2xl p-5 border border-border-default">
        <p className="text-caption text-content-muted uppercase tracking-wide mb-1">
          {t("vodafoneCashNumberLabel")}
        </p>
        <p className="text-h3 text-content-primary" dir="ltr">{settings.vodafone_cash_number}</p>
        <p className="text-caption text-content-destructive mt-2">{t("walletNotBankNote")}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex flex-col gap-2">
          <label className="text-label text-content-secondary">{t("amountLabel")}</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder={t("amountPlaceholder")}
            className="w-full rounded-xl border border-border-default bg-surface-bg px-4 py-3 text-body-sm text-content-primary"
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-label text-content-secondary">{t("paymentReferenceLabel")}</label>
          <input
            type="text"
            required
            value={paymentReference}
            onChange={(e) => setPaymentReference(e.target.value)}
            placeholder={t("paymentReferencePlaceholder")}
            className="w-full rounded-xl border border-border-default bg-surface-bg px-4 py-3 text-body-sm text-content-primary"
          />
        </div>

        <DocumentUpload label={t("screenshotLabel")} onFile={setScreenshot} required />
        <p className="text-caption text-content-muted">{t("screenshotHelp")}</p>

        {submitError && <p className="text-caption text-content-destructive">{submitError}</p>}

        <button
          type="submit"
          disabled={submitting || !amount || !paymentReference || !screenshot}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
        >
          {submitting && <Spinner />}
          {submitting ? t("submitting") : t("submit")}
        </button>
      </form>
    </div>
  );
}
