"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { submitWithdrawal } from "@/lib/api/wallet-withdrawal";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

export default function WalletWithdrawPage() {
  const router = useRouter();
  const t = useTranslations("driver.walletWithdraw");
  const [amount, setAmount] = useState("");
  const [payoutReference, setPayoutReference] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError("");
    try {
      const token = await getToken();
      await submitWithdrawal(token, amount, payoutReference);
      setSubmitted(true);
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string };
      const knownErrors = ["validation_error", "insufficient_balance", "pending_request_exists"];
      if (e?.error && knownErrors.includes(e.error)) {
        setSubmitError(t(`errors.${e.error}`));
      } else {
        setSubmitError(t("errors.generic"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="p-4 space-y-4 text-center">
        <h1 className="text-h3 text-content-primary">{t("pendingHeading")}</h1>
        <p className="text-body-sm text-content-secondary">{t("pendingBody")}</p>
        <button onClick={() => router.push("/wallet/withdraw/history")} className="text-body-sm text-brand-primary underline">
          {t("history.heading")}
        </button>
        <button onClick={() => router.push("/wallet")} className="block mx-auto text-body-sm text-content-muted underline">
          {t("backToWallet")}
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
          onClick={() => router.push("/wallet/withdraw/history")}
          className="text-body-sm text-brand-primary font-medium hover:underline whitespace-nowrap"
        >
          {t("history.heading")}
        </button>
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
          <label className="text-label text-content-secondary">{t("payoutReferenceLabel")}</label>
          <input
            type="text"
            required
            value={payoutReference}
            onChange={(e) => setPayoutReference(e.target.value)}
            placeholder={t("payoutReferencePlaceholder")}
            className="w-full rounded-xl border border-border-default bg-surface-bg px-4 py-3 text-body-sm text-content-primary"
          />
          <p className="text-caption text-content-muted">{t("payoutReferenceHelp")}</p>
        </div>

        {submitError && <p className="text-caption text-content-destructive">{submitError}</p>}

        <button
          type="submit"
          disabled={submitting || !amount || !payoutReference}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </form>
    </div>
  );
}
