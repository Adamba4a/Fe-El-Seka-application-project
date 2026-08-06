"use client";

import { useLocale, useTranslations } from "next-intl";
import { formatEgp } from "@/lib/api/wallet";
import type { Locale } from "@fe-el-seka/shared";

interface Props {
  balance_egp: string;
  reserved_egp: string;
  available_egp: string;
}

export function WalletBalanceCard({ balance_egp, reserved_egp, available_egp }: Props) {
  const t = useTranslations("walletBalanceCard");
  const locale = useLocale() as Locale;
  const hasReservation = reserved_egp !== "0.00";

  return (
    <div className="bg-surface-card rounded-2xl p-5 space-y-4 border border-border-default">
      <div className="text-center">
        <p className="text-body-sm text-content-muted mb-1">{t("availableBalance")}</p>
        <p className="text-3xl font-bold text-brand-primary">{formatEgp(available_egp, locale)}</p>
      </div>

      <div className="border-t border-border-default pt-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <p className="text-content-muted text-xs">{t("totalBalance")}</p>
          <p className="font-medium text-content-primary">{formatEgp(balance_egp, locale)}</p>
        </div>
        {hasReservation && (
          <div>
            <p className="text-content-muted text-xs">{t("reserved")}</p>
            <p className="font-medium text-yellow-600">{formatEgp(reserved_egp, locale)}</p>
          </div>
        )}
      </div>
    </div>
  );
}
