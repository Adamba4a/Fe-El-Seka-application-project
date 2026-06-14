"use client";

import { useState } from "react";

interface UserActionPanelProps {
  userId: string;
  currentStatus: string;
  onSuspend: (userId: string, reason: string) => Promise<void>;
  onReinstate: (userId: string) => Promise<void>;
}

export function UserActionPanel({ userId, currentStatus, onSuspend, onReinstate }: UserActionPanelProps) {
  const [suspendReason, setSuspendReason] = useState("");
  const [showSuspendForm, setShowSuspendForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isSuspended = currentStatus === "suspended";

  async function handleSuspend(e: React.FormEvent) {
    e.preventDefault();
    if (!suspendReason.trim()) { setError("Reason is required"); return; }
    setError("");
    setLoading(true);
    try {
      await onSuspend(userId, suspendReason.trim());
      setShowSuspendForm(false);
      setSuspendReason("");
    } finally {
      setLoading(false);
    }
  }

  async function handleReinstate() {
    if (!confirm("Reinstate this user?")) return;
    setLoading(true);
    try {
      await onReinstate(userId);
    } finally {
      setLoading(false);
    }
  }

  if (isSuspended) {
    return (
      <button
        onClick={handleReinstate}
        disabled={loading}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
      >
        {loading ? "Reinstating…" : "Reinstate User"}
      </button>
    );
  }

  if (!showSuspendForm) {
    return (
      <button
        onClick={() => setShowSuspendForm(true)}
        className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm font-medium"
      >
        Suspend User
      </button>
    );
  }

  return (
    <form onSubmit={handleSuspend} className="space-y-3 border border-red-200 rounded p-4 bg-red-50">
      <label className="block text-sm font-medium text-gray-700">
        Suspension reason <span className="text-red-500">*</span>
      </label>
      <textarea
        value={suspendReason}
        onChange={(e) => setSuspendReason(e.target.value)}
        rows={3}
        placeholder="Reason for suspending this user…"
        className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
        >
          {loading ? "Suspending…" : "Confirm Suspend"}
        </button>
        <button
          type="button"
          onClick={() => { setShowSuspendForm(false); setSuspendReason(""); setError(""); }}
          className="px-4 py-2 border rounded text-sm"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
