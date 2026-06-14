"use client";

import { useState } from "react";

interface UnlockButtonProps {
  userId: string;
  onUnlock: (userId: string) => Promise<void>;
}

export function UnlockButton({ userId, onUnlock }: UnlockButtonProps) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (!confirm("Unlock this user so they can resubmit verification documents?")) return;
    setLoading(true);
    try {
      await onUnlock(userId);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 disabled:opacity-50 text-sm font-medium"
    >
      {loading ? "Unlocking…" : "Unlock Resubmission"}
    </button>
  );
}
