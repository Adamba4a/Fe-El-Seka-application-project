"use client";

import { useState } from "react";

interface ApproveButtonProps {
  onApprove: () => Promise<void>;
}

export function ApproveButton({ onApprove }: ApproveButtonProps) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (!confirm("Approve this submission? This will mark the user as verified.")) return;
    setLoading(true);
    try {
      await onApprove();
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
    >
      {loading ? "Approving…" : "Approve"}
    </button>
  );
}
