const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function approveVehicleUpdate(token: string, requestId: string): Promise<void> {
  const res = await fetch(`${base}/api/admin/vehicle-updates/${requestId}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
}

export async function rejectVehicleUpdate(token: string, requestId: string, reason: string): Promise<void> {
  const res = await fetch(`${base}/api/admin/vehicle-updates/${requestId}/reject`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
}
