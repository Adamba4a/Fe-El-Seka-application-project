import { createAdminClient } from "@/lib/supabase/admin-client";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function VehicleUpdateQueuePage() {
  const supabase = createAdminClient();

  const { data } = await supabase
    .from("vehicle_update_requests")
    .select("id, driver_id, plate_number, make, model, year, submitted_at, profiles(display_name, email), vehicles(plate_number, make, model, year)")
    .eq("status", "pending_review")
    .order("submitted_at", { ascending: true });

  const items = (data ?? []) as any[];

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Vehicle Update Requests</h1>
        <Link href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
      </div>

      {items.length === 0 ? (
        <p className="text-gray-400">No pending vehicle update requests.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Link
              key={item.id}
              href={`/vehicles/${item.id}`}
              className="block border rounded-lg p-4 hover:bg-gray-50 space-y-1"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{item.profiles?.display_name ?? "Unknown"}</span>
                <span className="text-xs text-gray-400">{new Date(item.submitted_at).toLocaleString()}</span>
              </div>
              <p className="text-sm text-gray-500">{item.profiles?.email}</p>
              <div className="text-xs text-gray-600 flex gap-4 pt-1">
                {item.plate_number && <span>Plate: <span className="font-medium">{item.plate_number}</span></span>}
                {item.make && <span>Make: <span className="font-medium">{item.make}</span></span>}
                {item.model && <span>Model: <span className="font-medium">{item.model}</span></span>}
                {item.year && <span>Year: <span className="font-medium">{item.year}</span></span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
