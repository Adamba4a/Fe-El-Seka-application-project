"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import type { LedgerEntry } from "@/lib/api/wallet";
import { formatEgp } from "@/lib/api/wallet";

interface Props {
  entry: LedgerEntry;
}

function relativeTime(
  iso: string,
  t: (key: string, values?: Record<string, string | number>) => string
): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return t("justNow");
  if (mins < 60) return t("minutesAgo", { minutes: mins });
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return t("hoursAgo", { hours: hrs });
  const days = Math.floor(hrs / 24);
  if (days < 7) return t("daysAgo", { days });
  return new Date(iso).toLocaleDateString("en-EG", { day: "numeric", month: "short" });
}

export function LedgerEntryRow({ entry }: Props) {
  const t = useTranslations("ledgerEntryRow");
  const TYPE_LABELS: Record<LedgerEntry["type"], string> = {
    COMMISSION_DEBIT: t("commissionCharge"),
    ADMIN_CREDIT: t("balanceTopUp"),
    ADMIN_DEBIT: t("balanceAdjustment"),
  };
  const isCredit = entry.type === "ADMIN_CREDIT";
  const amountColor = isCredit ? "text-green-600" : "text-red-600";
  const sign = isCredit ? "+" : "−";

  return (
    <div className="flex items-center justify-between py-3 border-b border-border-default last:border-0">
      <div className="space-y-0.5">
        <p className="text-body-sm font-medium text-content-primary">
          {TYPE_LABELS[entry.type]}
        </p>
        <div className="flex items-center gap-2 text-xs text-content-muted">
          <span>{relativeTime(entry.created_at, t)}</span>
          {entry.ride_id && entry.type === "COMMISSION_DEBIT" && (
            <Link
              href={`/rides/${entry.ride_id}/manage`}
              className="text-brand-primary underline"
            >
              {t("viewRide")}
            </Link>
          )}
          {entry.note && <span>· {entry.note}</span>}
        </div>
      </div>
      <p className={`font-semibold text-body-sm ${amountColor}`}>
        {sign}{formatEgp(entry.amount_egp)}
      </p>
    </div>
  );
}
