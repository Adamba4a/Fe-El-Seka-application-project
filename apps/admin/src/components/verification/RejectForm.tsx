"use client";

import { useState } from "react";

interface RejectFormProps {
  attemptNumber: number;
  onReject: (reason: string) => Promise<void>;
}

export function RejectForm({ attemptNumber, onReject }: RejectFormProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isLastAttempt = attemptNumber >= 3;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) { setError("Reason is required"); return; }
    setError("");
    setLoading(true);
    try {
      await onReject(reason.trim());
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm font-medium"
      >
        Reject
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border border-red-200 rounded p-4 bg-red-50">
      {isLastAttempt && (
        <p className="text-sm font-medium text-red-700">
          This is attempt 3/3. Rejecting will lock the user from resubmitting.
        </p>
      )}
      <label className="block text-sm font-medium text-gray-700">
        Rejection reason <span className="text-red-500">*</span>
      </label>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={3}
        placeholder="Explain why this submission is rejected…"
        className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
        >
          {loading ? "Rejecting…" : "Confirm Reject"}
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
