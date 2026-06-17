import { notFound } from "next/navigation";
import Link from "next/link";
import { createAdminClient } from "@/lib/supabase/admin-client";
import { VehicleUpdateActions } from "./VehicleUpdateActions";

export const dynamic = "force-dynamic";

function DiffRow({ label, current, proposed }: { label: string; current?: string | number | null; proposed?: string | number | null }) {
  if (proposed == null) return null;
  const changed = String(proposed) !== String(current ?? "");
  return (
    <tr>
      <td className="py-1.5 pr-4 text-gray-500 text-sm">{label}</td>
      <td className="py-1.5 pr-4 text-sm line-through text-gray-400">{current ?? "—"}</td>
      <td className={`py-1.5 text-sm font-medium ${changed ? "text-amber-700" : "text-gray-600"}`}>{proposed}</td>
    </tr>
  );
}

export default async function VehicleUpdateDetailPage({ params }: { params: { request_id: string } }) {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("vehicle_update_requests")
    .select("*, profiles(display_name, email), vehicles(plate_number, make, model, year, color, seat_count)")
    .eq("id", params.request_id)
    .single();

  if (error || !data) notFound();

  const detail = data as any;
  const current = detail.vehicles;

  return (
    <main className="p-8 space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Link href="/vehicles" className="text-sm text-blue-600 hover:underline">← Vehicle Updates</Link>
      </div>

      <h1 className="text-xl font-semibold">Vehicle Update Request</h1>

      <dl className="grid grid-cols-2 gap-2 text-sm">
        <dt className="text-gray-500">Driver</dt><dd>{detail.profiles?.display_name ?? "—"}</dd>
        <dt className="text-gray-500">Email</dt><dd>{detail.profiles?.email ?? "—"}</dd>
        <dt className="text-gray-500">Submitted</dt><dd>{new Date(detail.submitted_at).toLocaleString()}</dd>
        <dt className="text-gray-500">Status</dt><dd className="capitalize">{detail.status.replace(/_/g, " ")}</dd>
      </dl>

      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Proposed Changes</h2>
        <table className="w-full border rounded-lg overflow-hidden text-sm">
          <thead>
            <tr className="bg-gray-100 text-xs text-gray-500">
              <th className="text-left p-2">Field</th>
              <th className="text-left p-2">Current</th>
              <th className="text-left p-2">Proposed</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            <DiffRow label="Plate Number" current={current?.plate_number} proposed={detail.plate_number} />
            <DiffRow label="Make" current={current?.make} proposed={detail.make} />
            <DiffRow label="Model" current={current?.model} proposed={detail.model} />
            <DiffRow label="Year" current={current?.year} proposed={detail.year} />
          </tbody>
        </table>
      </div>

      {detail.status === "pending_review" && (
        <VehicleUpdateActions requestId={params.request_id} />
      )}

      {detail.status !== "pending_review" && (
        <p className="text-sm text-gray-500 italic">
          This request has already been {detail.status}.
          {detail.rejection_reason && ` Reason: ${detail.rejection_reason}`}
        </p>
      )}
    </main>
  );
}
