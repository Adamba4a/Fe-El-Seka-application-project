"use client";

import { useState } from "react";

type Action = "warn" | "suspend" | "dismiss";

interface ResolveFormProps {
  onResolve: (action: Action, reason: string) => Promise<void>;
}

export function ResolveForm({ onResolve }: ResolveFormProps) {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<Action>("warn");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reason.trim()) { setError("Reason is required"); return; }
    setError("");
    setLoading(true);
    try {
      await onResolve(action, reason.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resolve report");
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium"
      >
        Resolve
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border border-blue-200 rounded p-4 bg-blue-50">
      <label className="block text-sm font-medium text-gray-700">Action</label>
      <select
        value={action}
        onChange={(e) => setAction(e.target.value as Action)}
        className="w-full border rounded px-3 py-2 text-sm"
      >
        <option value="warn">Warn</option>
        <option value="suspend">Suspend</option>
        <option value="dismiss">Dismiss</option>
      </select>
      <label className="block text-sm font-medium text-gray-700">
        Reason <span className="text-red-500">*</span>
      </label>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={3}
        placeholder="Explain the decision…"
        className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
        >
          {loading ? "Submitting…" : "Confirm"}
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
