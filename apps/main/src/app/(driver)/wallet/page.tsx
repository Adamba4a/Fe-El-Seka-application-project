"use client";

import { useEffect, useState, useCallback } from "react";
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
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const token = await getToken();
      const data = await getWallet(token, 1);
      setWallet(data);
    } catch {
      setError("Failed to load wallet.");
    }
  }, []);

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
  if (!wallet) return <p className="text-content-muted text-body-sm">Loading…</p>;

  const isEmpty = wallet.entries.length === 0;

  return (
    <div className="space-y-6">
      <h1 className="text-h3 text-content-primary">My Wallet</h1>

      <WalletBalanceCard
        balance_egp={wallet.balance_egp}
        reserved_egp={wallet.reserved_egp}
        available_egp={wallet.available_egp}
      />

      <section>
        <h2 className="text-body-sm font-semibold text-content-primary mb-3">
          Transaction History
        </h2>

        {isEmpty ? (
          <p className="text-body-sm text-content-muted">
            No transactions yet. Add balance to start posting rides.
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
