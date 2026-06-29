"use client";

import { useState } from "react";
import type { LedgerEntry } from "@/lib/api/wallet";
import { getWallet } from "@/lib/api/wallet";
import { LedgerEntryRow } from "./LedgerEntryRow";

interface Props {
  initialEntries: LedgerEntry[];
  initialTotalPages: number;
  getToken: () => Promise<string>;
}

export function LedgerEntryList({ initialEntries, initialTotalPages, getToken }: Props) {
  const [entries, setEntries] = useState<LedgerEntry[]>(initialEntries);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const hasMore = page < initialTotalPages;

  async function loadMore() {
    setLoading(true);
    try {
      const token = await getToken();
      const next = await getWallet(token, page + 1);
      setEntries((prev) => [...prev, ...next.entries]);
      setPage((p) => p + 1);
    } catch {
      // silently ignore — user can retry
    } finally {
      setLoading(false);
    }
  }

  if (entries.length === 0) return null;

  return (
    <div>
      <div className="divide-y divide-border-default">
        {entries.map((e) => (
          <LedgerEntryRow key={e.id} entry={e} />
        ))}
      </div>

      {hasMore && (
        <button
          onClick={loadMore}
          disabled={loading}
          className="mt-4 w-full text-brand-primary text-body-sm font-medium disabled:opacity-50"
        >
          {loading ? "Loading…" : "Load more"}
        </button>
      )}
    </div>
  );
}
