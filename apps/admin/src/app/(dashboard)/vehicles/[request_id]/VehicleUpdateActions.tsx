"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { approveVehicleUpdate, rejectVehicleUpdate } from "@/lib/api/admin-vehicles";

const sb = createAdminBrowserClient();

async function getToken(): Promise<string> {
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? "";
}

export function VehicleUpdateActions({ requestId }: { requestId: string }) {
  const router = useRouter();
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleApprove() {
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      await approveVehicleUpdate(token, requestId);
      router.push("/vehicles");
    } catch (err: any) {
      setError(err?.detail?.message ?? err?.message ?? "Failed to approve");
    } finally {
      setLoading(false);
    }
  }

  async function handleReject() {
    if (!rejectReason.trim()) return;
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      await rejectVehicleUpdate(token, requestId, rejectReason.trim());
      router.push("/vehicles");
    } catch (err: any) {
      setError(err?.detail?.message ?? err?.message ?? "Failed to reject");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-3">
        <button
          onClick={handleApprove}
          disabled={loading}
          className="px-5 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          onClick={() => setShowRejectForm(true)}
          disabled={loading}
          className="px-5 py-2 border border-red-300 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 disabled:opacity-50"
        >
          Reject
        </button>
      </div>

      {showRejectForm && (
        <div className="space-y-2">
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
            placeholder="Reason for rejection…"
            className="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => setShowRejectForm(false)}
              className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleReject}
              disabled={loading || !rejectReason.trim()}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-red-700"
            >
              {loading ? "Rejecting…" : "Confirm Reject"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
