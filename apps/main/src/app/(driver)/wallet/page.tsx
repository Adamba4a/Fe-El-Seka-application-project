"use client";

import { useEffect, useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { getWallet, type WalletResponse } from "@/lib/api/wallet";
import { WalletBalanceCard } from "@/components/wallet/WalletBalanceCard";
import { LedgerEntryList } from "@/components/wallet/LedgerEntryList";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

export default function WalletPage() {
  const t = useTranslations("driver.wallet");
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
      <div className="flex items-center justify-between">
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
        <Link
          href="/wallet/topup"
          className="rounded-xl bg-dash-primary px-4 py-2 text-body-sm font-semibold text-content-inverse hover:opacity-90 transition-opacity"
        >
          {t("addBalance")}
        </Link>
      </div>

      <WalletBalanceCard
        balance_egp={wallet.balance_egp}
        reserved_egp={wallet.reserved_egp}
        available_egp={wallet.available_egp}
      />

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
