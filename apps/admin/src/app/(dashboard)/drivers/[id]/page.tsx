"use client";

import Link from "next/link";

export default function DriverDetailPage({ params }: { params: { id: string } }) {
  return (
    <main className="p-8 space-y-6 max-w-xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Driver</h1>
        <span className="font-mono text-xs text-gray-400">{params.id}</span>
      </div>

      <nav className="flex gap-3">
        <Link
          href={`/drivers/${params.id}/wallet`}
          className="inline-flex items-center gap-2 px-4 py-2 rounded border border-gray-300 text-sm font-medium hover:bg-gray-50 transition-colors"
        >
          Wallet
        </Link>
      </nav>
    </main>
  );
}
