"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import {
  getLoyaltyBalance,
  getLoyaltyTransactions,
  getLoyaltyCatalog,
  type LoyaltyTransaction,
  type LoyaltyCatalogEntry,
} from "@/lib/api/loyalty";
import { VoucherRedeemSection } from "@/components/loyalty/VoucherRedeemSection";
import type { Locale } from "@fe-el-seka/shared";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

const KNOWN_REASONS = [
  "ride_completed_earn",
  "redemption_spend",
  "redemption_refund",
  "ride_reversal_clawback",
] as const;

function formatDate(iso: string, locale: Locale): string {
  return new Date(iso).toLocaleDateString(locale === "ar" ? "ar-EG" : "en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function LoyaltyPage() {
  const t = useTranslations("passenger.loyalty");
  const tc = useTranslations("common");
  const locale = useLocale() as Locale;
  const [balance, setBalance] = useState<number | null>(null);
  const [entries, setEntries] = useState<LoyaltyTransaction[]>([]);
  const [vouchers, setVouchers] = useState<LoyaltyCatalogEntry[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const PER_PAGE = 50;

  const load = useCallback(async () => {
    try {
      setError(null);
      const token = await getToken();
      const [balanceRes, txRes, catalogRes] = await Promise.all([
        getLoyaltyBalance(token),
        getLoyaltyTransactions(token, 1),
        getLoyaltyCatalog(token),
      ]);
      setBalance(balanceRes.balance);
      setEntries(txRes.items);
      setPage(1);
      setTotalPages(Math.max(1, Math.ceil(txRes.total / PER_PAGE)));
      setVouchers(catalogRes.items.filter((i) => i.type === "voucher"));
    } catch {
      setError(t("loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
    function handleVisibility() {
      if (document.visibilityState === "visible") load();
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [load]);

  async function loadMore() {
    setLoadingMore(true);
    try {
      const token = await getToken();
      const next = await getLoyaltyTransactions(token, page + 1);
      setEntries((prev) => [...prev, ...next.items]);
      setPage((p) => p + 1);
    } catch {
      // silently ignore — user can retry
    } finally {
      setLoadingMore(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-content-destructive">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <a
          href="/dashboard"
          aria-label={tc("back")}
          className="text-content-muted hover:text-content-secondary text-lg"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </a>
        <h1 className="text-h3 text-content-primary">{t("title")}</h1>
      </div>

      <div className="bg-surface-card rounded-2xl p-5 border border-border-default text-center">
        <p className="text-3xl font-bold text-brand-primary">{t("balance", { points: balance ?? 0 })}</p>
      </div>

      <VoucherRedeemSection
        t={t}
        vouchers={vouchers}
        balance={balance ?? 0}
        getToken={getToken}
        onRedeemed={load}
      />

      <section>
        <h2 className="text-body-sm font-semibold text-content-primary mb-3">
          {t("transactionHistory")}
        </h2>

        {entries.length === 0 ? (
          <p className="text-body-sm text-content-muted">{t("noTransactions")}</p>
        ) : (
          <div>
            <div className="divide-y divide-border-default">
              {entries.map((e) => (
                <div key={e.id} className="flex items-center justify-between py-3 text-sm">
                  <div>
                    <p className="font-medium text-content-primary">
                      {(KNOWN_REASONS as readonly string[]).includes(e.reason)
                        ? t(`reasons.${e.reason as (typeof KNOWN_REASONS)[number]}`)
                        : e.reason}
                    </p>
                    <p className="text-xs text-content-muted">{formatDate(e.created_at, locale)}</p>
                  </div>
                  <span
                    className={`font-semibold ${e.delta >= 0 ? "text-green-600" : "text-content-destructive"}`}
                  >
                    {e.delta >= 0 ? "+" : ""}
                    {e.delta}
                  </span>
                </div>
              ))}
            </div>

            {page < totalPages && (
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="mt-4 w-full text-brand-primary text-body-sm font-medium disabled:opacity-50"
              >
                {loadingMore ? t("loading") : t("showMore")}
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
