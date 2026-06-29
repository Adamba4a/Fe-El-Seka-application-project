"use client";

import { useEffect, useState } from "react";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getDriverWallet, type WalletData } from "@/lib/api/admin-wallet";
import { AdminWalletSummary } from "@/components/wallet/AdminWalletSummary";
import { TopUpForm } from "@/components/wallet/TopUpForm";
import { AdjustForm } from "@/components/wallet/AdjustForm";
import { AdminLedgerTable } from "@/components/wallet/AdminLedgerTable";

const sb = createAdminBrowserClient();

export default function DriverWalletPage({ params }: { params: { id: string } }) {
  const [wallet, setWallet] = useState<WalletData | null>(null);
  const [error, setError] = useState("");
  const [showTopUp, setShowTopUp] = useState(false);
  const [showAdjust, setShowAdjust] = useState(false);

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  async function load() {
    try {
      const token = await getToken();
      const data = await getDriverWallet(token, params.id);
      setWallet(data);
    } catch {
      setError("Failed to load wallet data.");
    }
  }

  useEffect(() => { load(); }, [params.id]);

  function handleMutationSuccess() {
    setShowTopUp(false);
    setShowAdjust(false);
    load();
  }

  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!wallet) return <main className="p-8 text-gray-400">Loading…</main>;

  return (
    <main className="p-8 space-y-8 max-w-3xl">
      <h1 className="text-xl font-semibold">Driver Wallet</h1>
      <p className="text-xs text-gray-400 font-mono">{wallet.driver_id}</p>

      <AdminWalletSummary
        balance_egp={wallet.balance_egp}
        reserved_egp={wallet.reserved_egp}
        available_egp={wallet.available_egp}
      />

      <div className="space-y-4">
        <div className="border rounded">
          <button
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-left"
            onClick={() => { setShowTopUp((v) => !v); setShowAdjust(false); }}
          >
            <span>Top Up Wallet</span>
            <span>{showTopUp ? "▲" : "▼"}</span>
          </button>
          {showTopUp && (
            <div className="px-4 pb-4 border-t">
              <WalletFormWithToken
                driverId={params.id}
                getToken={getToken}
                onSuccess={handleMutationSuccess}
                type="topup"
                availableEgp={wallet.available_egp}
              />
            </div>
          )}
        </div>

        <div className="border rounded">
          <button
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-left"
            onClick={() => { setShowAdjust((v) => !v); setShowTopUp(false); }}
          >
            <span>Debit Wallet</span>
            <span>{showAdjust ? "▲" : "▼"}</span>
          </button>
          {showAdjust && (
            <div className="px-4 pb-4 border-t">
              <WalletFormWithToken
                driverId={params.id}
                getToken={getToken}
                onSuccess={handleMutationSuccess}
                type="adjust"
                availableEgp={wallet.available_egp}
              />
            </div>
          )}
        </div>
      </div>

      <section>
        <h2 className="text-sm font-semibold mb-3">
          Transaction History ({wallet.pagination.total_entries})
        </h2>
        <AdminLedgerTable entries={wallet.entries} />
      </section>
    </main>
  );
}

function WalletFormWithToken({
  driverId,
  getToken,
  onSuccess,
  type,
  availableEgp,
}: {
  driverId: string;
  getToken: () => Promise<string>;
  onSuccess: () => void;
  type: "topup" | "adjust";
  availableEgp: string;
}) {
  const [token, setToken] = useState("");
  useEffect(() => { getToken().then(setToken); }, []);

  if (!token) return <p className="text-sm text-gray-400 py-3">Loading…</p>;

  if (type === "topup") {
    return <TopUpForm token={token} driverId={driverId} onSuccess={onSuccess} />;
  }
  return (
    <AdjustForm
      token={token}
      driverId={driverId}
      availableEgp={availableEgp}
      onSuccess={onSuccess}
    />
  );
}
