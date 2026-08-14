"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { getHistory, cancelRequest, type TopupHistoryItem } from "@/lib/api/wallet-topup";
import { formatEgp } from "@/lib/api/wallet";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Spinner } from "@/components/ui/Spinner";
import type { Locale } from "@fe-el-seka/shared";

const supabase = createClient();

async function getToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

const STATUS_STYLES: Record<TopupHistoryItem["status"], string> = {
  PENDING: "bg-status-scheduled-bg text-status-scheduled",
  APPROVED: "bg-status-completed-bg text-status-completed",
  REJECTED: "bg-status-cancelled-bg text-status-cancelled",
  CANCELLED: "bg-status-cancelled-bg text-status-cancelled",
};

export default function WalletTopupHistoryPage() {
  const router = useRouter();
  const t = useTranslations("driver.walletTopup.history");
  const locale = useLocale() as Locale;

  const [items, setItems] = useState<TopupHistoryItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const [cancelTarget, setCancelTarget] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      const res = await getHistory(token, 1);
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
      const res = await getHistory(token, page + 1);
      setItems((prev) => [...prev, ...res.items]);
      setPage((p) => p + 1);
      setTotalPages(res.pagination.total_pages);
    } catch {
      // silently ignore — user can retry via the button
    } finally {
      setLoadingMore(false);
    }
  }

  function openCancelSheet(id: string) {
    setCancelError("");
    setCancelTarget(id);
  }

  function closeCancelSheet() {
    setCancelTarget(null);
    setCancelError("");
  }

  async function handleCancel() {
    if (!cancelTarget) return;
    setCancelling(true);
    setCancelError("");
    try {
      const token = await getToken();
      await cancelRequest(token, cancelTarget);
      setCancelTarget(null);
      await load();
    } catch {
      setCancelError(t("cancelError"));
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="p-4 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-h3 text-content-primary">{t("heading")}</h1>
        <button onClick={() => router.push("/wallet/topup")} className="text-body-sm text-brand-primary underline">
          {t("backToTopup")}
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
                {item.payment_reference}
              </p>
              {item.status === "REJECTED" && item.rejection_reason && (
                <p className="text-caption text-content-destructive">
                  {t("rejectionReasonPrefix", { reason: item.rejection_reason })}
                </p>
              )}
              {item.status === "PENDING" && (
                <button
                  onClick={() => openCancelSheet(item.id)}
                  className="text-caption text-content-destructive underline"
                >
                  {t("cancelAction")}
                </button>
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

      <BottomSheet isOpen={cancelTarget !== null} onClose={closeCancelSheet}>
        <div className="space-y-4">
          <h2 className="text-h3 text-content-primary">{t("cancelSheetTitle")}</h2>
          <p className="text-body-sm text-content-muted">{t("cancelSheetBody")}</p>
          {cancelError && <p className="text-caption text-content-destructive">{cancelError}</p>}
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-surface-destructive text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
          >
            {cancelling && <Spinner />}
            {cancelling ? t("cancelling") : t("confirmCancellation")}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
