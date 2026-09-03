"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { getWallet, type WalletResponse } from "@/lib/api/wallet";
import { LedgerEntryList } from "@/components/wallet/LedgerEntryList";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

export default function WalletHistoryPage() {
  const router = useRouter();
  const t = useTranslations("driver.wallet");
  const tc = useTranslations("common");
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const data = await getWallet(token, 1);
        setWallet(data);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : JSON.stringify(err);
        setError(t("loadFailedPrefix", { message: msg }));
      }
    })();
  }, [t]);

  return (
    <div className="p-4 space-y-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          aria-label={tc("back")}
          className="text-content-muted hover:text-content-secondary text-lg"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <h1 className="text-h3 text-content-primary">{t("transactionHistory")}</h1>
      </div>

      {error && <p className="text-content-destructive text-body-sm">{error}</p>}
      {!error && !wallet && <p className="text-content-muted text-body-sm">{t("loading")}</p>}
      {wallet && wallet.entries.length === 0 && (
        <p className="text-content-muted text-body-sm">{t("noTransactions")}</p>
      )}
      {wallet && wallet.entries.length > 0 && (
        <LedgerEntryList
          initialEntries={wallet.entries}
          initialTotalPages={wallet.pagination.total_pages}
          getToken={getToken}
        />
      )}
    </div>
  );
}
