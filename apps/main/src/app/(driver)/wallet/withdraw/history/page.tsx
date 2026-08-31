"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { getWithdrawalHistory, type WithdrawalHistoryItem } from "@/lib/api/wallet-withdrawal";
import { formatEgp } from "@/lib/api/wallet";
import type { Locale } from "@fe-el-seka/shared";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

const STATUS_STYLES: Record<WithdrawalHistoryItem["status"], string> = {
  PENDING: "bg-status-scheduled-bg text-status-scheduled",
  APPROVED: "bg-status-completed-bg text-status-completed",
  REJECTED: "bg-status-cancelled-bg text-status-cancelled",
};

export default function WalletWithdrawHistoryPage() {
  const router = useRouter();
  const t = useTranslations("driver.walletWithdraw.history");
  const locale = useLocale() as Locale;

  const [items, setItems] = useState<WithdrawalHistoryItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      const res = await getWithdrawalHistory(token, 1);
      setItems(res.items);
      setPage(1);
      setTotalPages(res.pagination.total_pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : JSON.stringify(err);
      setError(t("loadFailedPrefix", { message: msg }));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  async function loadMore() {
    setLoadingMore(true);
    try {
      const token = await getToken();
      const res = await getWithdrawalHistory(token, page + 1);
      setItems((prev) => [...prev, ...res.items]);
      setPage((p) => p + 1);
      setTotalPages(res.pagination.total_pages);
    } catch {
      // silently ignore — user can retry via the button
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="p-4 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
        <button onClick={() => router.push("/wallet/withdraw")} className="text-body-sm text-brand-primary underline">
          {t("backToWithdraw")}
        </button>
      </div>

      {loading && <p className="text-content-muted text-body-sm">{t("loading")}</p>}
      {error && <p className="text-content-destructive text-body-sm">{error}</p>}

      {!loading && !error && items.length === 0 && (
        <p className="text-content-muted text-body-sm">{t("empty")}</p>
      )}

      {!loading && items.length > 0 && (
        <div className="divide-y divide-border-default">
          {items.map((item) => (
            <div key={item.id} className="py-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <p className="text-body-sm font-semibold text-content-primary">
                  {formatEgp(item.amount_egp, locale)}
                </p>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[item.status]}`}
                >
                  {t(`statuses.${item.status}`)}
                </span>
              </div>
              <p className="text-caption text-content-muted" dir="ltr">
                {item.payout_reference}
              </p>
              {item.status === "REJECTED" && item.rejection_reason && (
                <p className="text-caption text-content-destructive">
                  {t("rejectionReasonPrefix", { reason: item.rejection_reason })}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {!loading && page < totalPages && (
        <button
          onClick={loadMore}
          disabled={loadingMore}
          className="w-full text-brand-primary text-body-sm font-medium disabled:opacity-50"
        >
          {loadingMore ? t("loading") : t("loadMore")}
        </button>
      )}
    </div>
  );
}
