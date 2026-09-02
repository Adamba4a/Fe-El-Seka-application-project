"use client";

import { useEffect, useState, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { getWallet, formatEgp, type WalletResponse } from "@/lib/api/wallet";
import { WalletBalanceCard } from "@/components/wallet/WalletBalanceCard";
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
        <h2 className="text-body-sm font-semibold text-content-primary">{t("cashBackHeading")}</h2>
        <p className="text-caption text-content-muted">{t("cashBackHelp")}</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-surface-card rounded-2xl p-4 border border-border-default text-center space-y-2">
            <p className="text-body-sm text-content-muted">{t("cashBackPointsLabel")}</p>
            <p className="text-2xl font-bold text-content-primary">
              {formatEgp(wallet.cash_back_points_egp, locale)}
            </p>
            <Link
              href="/wallet/cash-back/redeem"
              className="inline-block text-body-sm text-brand-primary font-semibold hover:underline"
            >
              {t("redeemPoints")}
            </Link>
          </div>
          <div className="bg-surface-card rounded-2xl p-4 border border-border-default text-center space-y-2">
            <p className="text-body-sm text-content-muted">{t("cashBackBalance")}</p>
            <p className="text-2xl font-bold text-brand-primary">
              {formatEgp(wallet.sponsored_earnings_egp, locale)}
            </p>
            <Link
              href="/wallet/withdraw"
              className="inline-block text-body-sm text-content-primary font-semibold hover:underline"
            >
              {t("requestWithdrawal")}
            </Link>
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-body-sm font-semibold text-content-primary">
            {t("transactionHistory")}
          </h2>
          {!isEmpty && (
            <Link
              href="/wallet/history"
              className="text-body-sm text-brand-primary font-medium hover:underline whitespace-nowrap"
            >
              {t("viewHistory")}
            </Link>
          )}
        </div>

        {isEmpty && (
          <p className="text-body-sm text-content-muted mt-3">
            {t("noTransactions")}
          </p>
        )}
      </section>
    </div>
  );
}
