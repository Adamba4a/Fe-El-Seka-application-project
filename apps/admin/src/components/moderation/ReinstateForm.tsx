"use client";

import { useState } from "react";

interface ReinstateFormProps {
  onReinstate: (reason: string) => Promise<void>;
}

export function ReinstateForm({ onReinstate }: ReinstateFormProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) { setError("Reason is required"); return; }
    setError("");
    setLoading(true);
    try {
      await onReinstate(reason.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reinstate user");
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 text-sm font-medium"
      >
        Reinstate
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border border-yellow-200 rounded p-4 bg-yellow-50">
      <label className="block text-sm font-medium text-gray-700">
        Reason <span className="text-red-500">*</span>
      </label>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        placeholder="Explain why this user is being reinstated…"
        className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-400"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 disabled:opacity-50 text-sm font-medium"
        >
          {loading ? "Reinstating…" : "Confirm Reinstate"}
        </button>
        <button
          type="button"
          onClick={() => { setOpen(false); setReason(""); setError(""); }}
          className="px-4 py-2 border rounded text-sm"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
