"use client";

import { useState } from "react";
import { redeemLoyaltyCatalogEntry, type LoyaltyCatalogEntry } from "@/lib/api/loyalty";

interface VoucherRedeemSectionProps {
  t: (key: string, values?: Record<string, string | number>) => string;
  vouchers: LoyaltyCatalogEntry[];
  balance: number;
  getToken: () => Promise<string>;
  onRedeemed: () => void | Promise<void>;
}

export function VoucherRedeemSection({ t, vouchers, balance, getToken, onRedeemed }: VoucherRedeemSectionProps) {
  const [redeemingId, setRedeemingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleRedeem(entry: LoyaltyCatalogEntry) {
    setRedeemingId(entry.id);
    setMessage(null);
    try {
      const token = await getToken();
      const result = await redeemLoyaltyCatalogEntry(token, entry.id);
      setMessage(result.status === "fulfilled" ? t("redeemFulfilled") : t("redeemPending"));
      await onRedeemed();
    } catch {
      setMessage(t("redeemFailed"));
    } finally {
      setRedeemingId(null);
    }
  }

  if (vouchers.length === 0) {
    return (
      <section className="space-y-2">
        <h2 className="text-body-sm font-semibold text-content-primary">{t("redeemHeading")}</h2>
        <p className="text-body-sm text-content-muted">{t("noVouchers")}</p>
      </section>
    );
  }

  return (
    <section className="space-y-2">
      <h2 className="text-body-sm font-semibold text-content-primary">{t("redeemHeading")}</h2>
      <div className="space-y-3">
        {vouchers.map((entry) => {
          const canRedeem = balance >= entry.point_cost;
          return (
            <div
              key={entry.id}
              className="bg-surface-card rounded-2xl p-5 border border-border-default space-y-3"
            >
              <div>
                <p className="text-body-sm font-medium text-content-primary">{entry.title}</p>
                <p className="text-caption text-content-muted">{entry.description}</p>
              </div>
              <button
                onClick={() => handleRedeem(entry)}
                disabled={!canRedeem || redeemingId === entry.id}
                className="w-full rounded-xl bg-brand-primary px-4 py-2 text-body-sm font-semibold text-content-inverse hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {redeemingId === entry.id
                  ? t("redeeming")
                  : canRedeem
                    ? t("redeemVoucher", { points: entry.point_cost, title: entry.title })
                    : t("insufficientPoints")}
              </button>
            </div>
          );
        })}
      </div>
      {message && <p className="text-caption text-content-muted">{message}</p>}
    </section>
  );
}
