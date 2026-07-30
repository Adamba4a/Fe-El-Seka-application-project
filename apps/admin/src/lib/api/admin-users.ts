const base = process.env.NEXT_PUBLIC_API_URL!;

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function suspend(token: string, userId: string, reason: string): Promise<{ new_status: string }> {
  const res = await fetch(`${base}/api/admin/users/${userId}/suspend`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function reinstate(token: string, userId: string): Promise<{ new_status: string }> {
  const res = await fetch(`${base}/api/admin/users/${userId}/reinstate`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
