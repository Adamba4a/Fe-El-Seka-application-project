"use client";

import { useState } from "react";
import { adjustWallet } from "@/lib/api/admin-wallet";

interface Props {
  token: string;
  driverId: string;
  availableEgp: string;
  onSuccess: () => void;
}

export function AdjustForm({ token, driverId, availableEgp, onSuccess }: Props) {
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const parsed = parseFloat(amount);
    if (!parsed || parsed <= 0) {
      setError("Amount must be greater than 0.00 EGP");
      return;
    }
    setLoading(true);
    try {
      const result = await adjustWallet(token, driverId, parsed, note || undefined);
      setToast(`Adjusted. New balance: ${result.new_balance_egp} EGP`);
      setAmount("");
      setNote("");
      onSuccess();
      setTimeout(() => setToast(""), 4000);
    } catch (err: unknown) {
      const detail = err as { error?: string; available_egp?: string; message?: string };
      if (detail?.error === "DEBIT_EXCEEDS_AVAILABLE_BALANCE") {
        setError(`Exceeds available balance. Max debit: ${detail.available_egp} EGP`);
      } else {
        setError(detail?.message ?? "Adjustment failed");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <p className="text-xs text-gray-500">Max debit: {availableEgp} EGP</p>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Amount (EGP)</label>
        <input
          type="number"
          min="0.01"
          step="0.01"
          max={availableEgp}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Note (optional)</label>
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
          maxLength={200}
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {toast && <p className="text-sm text-green-600">{toast}</p>}
      <button
        type="submit"
        disabled={loading}
        className="bg-red-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
      >
        {loading ? "Processing…" : "Debit Wallet"}
      </button>
    </form>
  );
}
