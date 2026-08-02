"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import {
  getDashboardOverview,
  type DashboardOverview,
  type Period,
} from "@/lib/api/admin-dashboard";

const sb = createAdminBrowserClient();

const PERIODS: { value: Period; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
];

export default function DashboardPage() {
  const [period, setPeriod] = useState<Period>("7d");
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    (async () => {
      try {
        const { data: session } = await sb.auth.getSession();
        const token = session.session?.access_token ?? "";
        const overview = await getDashboardOverview(token, period);
        if (!cancelled) setData(overview);
      } catch {
        if (!cancelled) setError("Failed to load dashboard data.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [period]);

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Admin Dashboard</h1>
        <div className="flex gap-2">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1.5 rounded text-sm border ${
                period === p.value
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white hover:bg-gray-50"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!data && !error && <p className="text-sm text-gray-400">Loading…</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Link href="/users" className="block border rounded-lg p-5 hover:bg-gray-50">
              <p className="text-3xl font-bold">
                {data.users_by_role.passenger + data.users_by_role.driver + data.users_by_role.admin}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                Total users ({data.users_by_role.passenger} passengers, {data.users_by_role.driver} drivers)
              </p>
            </Link>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{data.rides_created}</p>
              <p className="text-sm text-gray-500 mt-1">Rides created</p>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{data.rides_completed}</p>
              <p className="text-sm text-gray-500 mt-1">Rides completed</p>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{data.commission_collected_egp} EGP</p>
              <p className="text-sm text-gray-500 mt-1">Commission collected</p>
            </div>
            <Link href="/verification" className="block border rounded-lg p-5 hover:bg-gray-50">
              <p className="text-3xl font-bold">{data.pending_verifications}</p>
              <p className="text-sm text-gray-500 mt-1">Pending verifications</p>
            </Link>
            <Link href="/moderation" className="block border rounded-lg p-5 hover:bg-gray-50">
              <p className="text-3xl font-bold">{data.open_reports}</p>
              <p className="text-sm text-gray-500 mt-1">Open reports</p>
            </Link>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{data.drivers_at_or_below_zero}</p>
              <p className="text-sm text-gray-500 mt-1">Drivers at/below zero balance</p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="border rounded-lg p-5">
              <p className="text-sm font-medium mb-3">Rides completed</p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={data.trends.rides_completed.points}>
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#111827" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-sm font-medium mb-3">Commission collected (EGP)</p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart
                  data={data.trends.commission_collected_egp.points.map((p) => ({
                    date: p.date,
                    value: Number(p.value),
                  }))}
                >
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#111827" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
