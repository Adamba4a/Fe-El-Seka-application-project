"use client";

import { useEffect, useState, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { getWallet, formatEgp, type WalletResponse } from "@/lib/api/wallet";
import { WalletBalanceCard } from "@/components/wallet/WalletBalanceCard";
import { LedgerEntryList } from "@/components/wallet/LedgerEntryList";
import type { Locale } from "@fe-el-seka/shared";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

export default function WalletPage() {
  const t = useTranslations("driver.wallet");
  const locale = useLocale() as Locale;
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const token = await getToken();
      const data = await getWallet(token, 1);
      setWallet(data);
    } catch (err: unknown) {
      const msg = err instanceof Error
        ? err.message
        : JSON.stringify(err);
      setError(t("loadFailedPrefix", { message: msg }));
    }
  }, [t]);

  useEffect(() => {
    load();

    // Refetch when the tab regains focus — balance may have changed after ride creation
    function handleVisibility() {
      if (document.visibilityState === "visible") load();
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [load]);

  if (error) return <p className="text-red-500 text-body-sm">{error}</p>;
  if (!wallet) return <p className="text-content-muted text-body-sm">{t("loading")}</p>;

  const isEmpty = wallet.entries.length === 0;

  return (
    <div className="space-y-6">
      <h1 className="text-h3 text-content-primary">{t("heading")}</h1>

      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-body-sm font-semibold text-content-primary">{t("cashWalletHeading")}</h2>
          <Link
            href="/wallet/topup"
            className="rounded-xl bg-dash-primary px-4 py-2 text-body-sm font-semibold text-content-inverse hover:opacity-90 transition-opacity"
          >
            {t("addBalance")}
          </Link>
        </div>
        <p className="text-caption text-content-muted">{t("cashWalletHelp")}</p>
        <WalletBalanceCard
          balance_egp={wallet.balance_egp}
          reserved_egp={wallet.reserved_egp}
          available_egp={wallet.available_egp}
        />
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-body-sm font-semibold text-content-primary">{t("sponsoredEarningsHeading")}</h2>
          <Link
            href="/wallet/withdraw"
            className="rounded-xl border border-border-default px-4 py-2 text-body-sm font-semibold text-content-primary hover:bg-surface-bg transition-colors"
          >
            {t("requestWithdrawal")}
          </Link>
        </div>
        <p className="text-caption text-content-muted">{t("sponsoredEarningsHelp")}</p>
        <div className="bg-surface-card rounded-2xl p-5 border border-border-default text-center">
          <p className="text-body-sm text-content-muted mb-1">{t("sponsoredEarningsBalance")}</p>
          <p className="text-3xl font-bold text-brand-primary">
            {formatEgp(wallet.sponsored_earnings_egp, locale)}
          </p>
        </div>
      </section>

      <section>
        <h2 className="text-body-sm font-semibold text-content-primary mb-3">
          {t("transactionHistory")}
        </h2>

        {isEmpty ? (
          <p className="text-body-sm text-content-muted">
            {t("noTransactions")}
          </p>
        ) : (
          <LedgerEntryList
            initialEntries={wallet.entries}
            initialTotalPages={wallet.pagination.total_pages}
            getToken={getToken}
          />
        )}
      </section>
    </div>
  );
}
