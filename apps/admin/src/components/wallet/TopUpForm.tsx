"use client";

import { useState } from "react";
import { topupWallet } from "@/lib/api/admin-wallet";

interface Props {
  token: string;
  driverId: string;
  onSuccess: () => void;
}

export function TopUpForm({ token, driverId, onSuccess }: Props) {
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
      const result = await topupWallet(token, driverId, parsed, note || undefined);
      setToast(`Topped up. New balance: ${result.new_balance_egp} EGP`);
      setAmount("");
      setNote("");
      onSuccess();
      setTimeout(() => setToast(""), 4000);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Top-up failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Amount (EGP)</label>
        <input
          type="number"
          min="0.01"
          step="0.01"
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
        className="bg-green-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
      >
        {loading ? "Processing…" : "Top Up"}
      </button>
    </form>
  );
}
