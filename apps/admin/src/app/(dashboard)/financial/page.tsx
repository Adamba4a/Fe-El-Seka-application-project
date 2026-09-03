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
  getReport,
  getDriverBalances,
  getReportExportUrl,
  type FinancialReport,
  type DriverBalanceItem,
} from "@/lib/api/admin-financial";

const sb = createAdminBrowserClient();

function toIsoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

const DEFAULT_END = new Date();
const DEFAULT_START = new Date(DEFAULT_END.getTime() - 6 * 24 * 60 * 60 * 1000);

export default function FinancialPage() {
  const [start, setStart] = useState(toIsoDate(DEFAULT_START));
  const [end, setEnd] = useState(toIsoDate(DEFAULT_END));
  const [report, setReport] = useState<FinancialReport | null>(null);
  const [drivers, setDrivers] = useState<DriverBalanceItem[]>([]);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  useEffect(() => {
    let cancelled = false;
    setError("");
    (async () => {
      try {
        const token = await getToken();
        const [reportRes, balancesRes] = await Promise.all([
          getReport(token, start, end),
          getDriverBalances(token),
        ]);
        if (!cancelled) {
          setReport(reportRes);
          setDrivers(balancesRes.items);
        }
      } catch {
        if (!cancelled) setError("Failed to load financial data.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start, end]);

  async function handleExport() {
    setExporting(true);
    try {
      const token = await getToken();
      const res = await fetch(getReportExportUrl(start, end), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `financial_report_${start}_${end}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Failed to export CSV.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
        <h1 className="text-2xl font-semibold">Financial Reporting</h1>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block text-gray-500 mb-1">Start</span>
          <input
            type="date"
            value={start}
            max={end}
            onChange={(e) => setStart(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="block text-gray-500 mb-1">End</span>
          <input
            type="date"
            value={end}
            min={start}
            onChange={(e) => setEnd(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm"
          />
        </label>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-3 py-1.5 rounded text-sm border bg-white hover:bg-gray-50 disabled:text-gray-400"
        >
          {exporting ? "Exporting…" : "Export CSV"}
        </button>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!report && !error && <p className="text-sm text-gray-400">Loading…</p>}

      {report && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{report.commission_collected_egp} EGP</p>
              <p className="text-sm text-gray-500 mt-1">Net commission (cash rides)</p>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{report.sponsored_commission_collected_egp} EGP</p>
              <p className="text-sm text-gray-500 mt-1">Net commission (sponsored rides)</p>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold text-gray-400">{report.distance_fee_passthrough_egp} EGP</p>
              <p className="text-sm text-gray-500 mt-1">Distance fee (returned to drivers as Cash Back — not revenue)</p>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{report.admin_credits_egp} EGP</p>
              <p className="text-sm text-gray-500 mt-1">Admin credits</p>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{report.admin_debits_egp} EGP</p>
              <p className="text-sm text-gray-500 mt-1">Admin debits</p>
            </div>
            <div className="border rounded-lg p-5">
              <p className="text-3xl font-bold">{report.net_revenue_egp} EGP</p>
              <p className="text-sm text-gray-500 mt-1">Net revenue</p>
            </div>
          </div>

          <div className="border rounded-lg p-5">
            <p className="text-sm font-medium mb-3">
              Commission collected (EGP, {report.trend.granularity === "week" ? "weekly" : "daily"})
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart
                data={report.trend.points.map((p) => ({ date: p.date, value: Number(p.value) }))}
              >
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#111827" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3">Sponsored Commission by Group</h2>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-2 pr-4 font-medium">Sponsored group</th>
                  <th className="pb-2 pr-4 font-medium">Commission collected</th>
                  <th className="pb-2 font-medium">Rides</th>
                </tr>
              </thead>
              <tbody>
                {report.sponsored_commission_by_group.map((g) => (
                  <tr key={g.group_id} className="border-b">
                    <td className="py-3 pr-4">{g.group_name}</td>
                    <td className="py-3 pr-4">{g.commission_egp} EGP</td>
                    <td className="py-3">{g.rides}</td>
                  </tr>
                ))}
                {report.sponsored_commission_by_group.length === 0 && (
                  <tr><td colSpan={3} className="py-8 text-center text-gray-400">No sponsored ride activity in this range</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3">Driver Balances</h2>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-2 pr-4 font-medium">Driver</th>
                  <th className="pb-2 pr-4 font-medium">Cash balance</th>
                  <th className="pb-2 pr-4 font-medium">Reserved</th>
                  <th className="pb-2 pr-4 font-medium">Available</th>
                  <th className="pb-2 pr-4 font-medium">Sponsored earnings (withdrawable)</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {drivers.map((d) => (
                  <tr key={d.driver_id} className="border-b">
                    <td className="py-3 pr-4">{d.display_name}</td>
                    <td className="py-3 pr-4">{d.balance_egp} EGP</td>
                    <td className="py-3 pr-4">{d.reserved_egp} EGP</td>
                    <td className="py-3 pr-4">{d.available_egp} EGP</td>
                    <td className="py-3 pr-4">{d.sponsored_earnings_egp} EGP</td>
                    <td className="py-3">
                      {d.is_at_risk && (
                        <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-medium">
                          At risk
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {drivers.length === 0 && (
                  <tr><td colSpan={6} className="py-8 text-center text-gray-400">No drivers yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
