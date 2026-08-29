"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import { getDetail, suspend, reinstate, type UserDetail } from "@/lib/api/admin-users";
import { UserActionPanel } from "@/components/users/UserActionPanel";

const sb = createAdminBrowserClient();

export default function UserDetailPage({ params }: { params: { user_id: string } }) {
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [error, setError] = useState("");

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  async function load() {
    try {
      const token = await getToken();
      const data = await getDetail(token, params.user_id);
      setDetail(data);
    } catch {
      setError("User not found");
    }
  }

  useEffect(() => {
    load();
  }, [params.user_id]);

  async function handleSuspend(userId: string, reason: string) {
    const token = await getToken();
    await suspend(token, userId, reason);
    await load();
  }

  async function handleReinstate(userId: string) {
    const token = await getToken();
    await reinstate(token, userId);
    await load();
  }

  if (error) return <main className="p-8 text-red-600">{error}</main>;
  if (!detail) return <main className="p-8 text-gray-400">Loading…</main>;

  const { profile, rides, bookings, ratings_received, reports, wallet, vehicle } = detail;

  return (
    <main className="p-8 space-y-8 max-w-3xl">
      <div className="flex items-center gap-4">
        <Link href="/users" className="text-sm text-blue-600 hover:underline">← Users</Link>
        <h1 className="text-xl font-semibold">User Detail</h1>
      </div>

      <section className="space-y-3">
        <div className="flex items-start gap-4">
          {profile.profile_photo_signed_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={profile.profile_photo_signed_url}
              alt="Profile"
              className="w-20 h-20 rounded-full object-cover border"
            />
          )}
          <dl className="grid grid-cols-2 gap-2 text-sm flex-1">
            <dt className="text-gray-500">User ID</dt>
            <dd className="flex items-center gap-2">
              <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded select-all">{profile.user_id}</code>
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(profile.user_id)}
                className="text-xs text-blue-600 hover:underline"
              >
                Copy
              </button>
            </dd>
            <dt className="text-gray-500">Name</dt><dd>{profile.display_name || "—"}</dd>
            <dt className="text-gray-500">Email</dt><dd>{profile.email}</dd>
            <dt className="text-gray-500">Phone</dt><dd>{profile.phone_number ?? "—"}</dd>
            <dt className="text-gray-500">Role</dt><dd className="capitalize">{profile.role}</dd>
            <dt className="text-gray-500">Status</dt>
            <dd>
              <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${
                profile.verification_status === "verified" ? "bg-green-100 text-green-700" :
                profile.verification_status === "suspended" ? "bg-red-100 text-red-700" :
                "bg-yellow-100 text-yellow-700"
              }`}>
                {profile.verification_status.replace(/_/g, " ")}
              </span>
            </dd>
            <dt className="text-gray-500">Org access</dt>
            <dd>
              {profile.org_verified_at ? (
                <>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                    Verified
                  </span>
                  {profile.org_verified_domain && (
                    <span className="text-gray-500 ml-2">{profile.org_verified_domain}</span>
                  )}
                  <span className="text-gray-400 ml-2">
                    ({new Date(profile.org_verified_at).toLocaleString()})
                  </span>
                </>
              ) : (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                  Not verified
                </span>
              )}
            </dd>
            <dt className="text-gray-500">Joined</dt><dd>{new Date(profile.created_at).toLocaleString()}</dd>
          </dl>
        </div>

        {profile.role === "driver" && (
          <a
            href={`/drivers/${profile.user_id}/wallet`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded border border-gray-300 text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            Manage Wallet
          </a>
        )}

        {!profile.is_admin_role && (
          <UserActionPanel
            userId={profile.user_id}
            currentStatus={profile.verification_status}
            onSuspend={handleSuspend}
            onReinstate={handleReinstate}
          />
        )}
      </section>

      {profile.role === "driver" && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Vehicle</h2>
          {!vehicle ? (
            <p className="text-sm text-gray-400">No vehicle registered.</p>
          ) : (
            <dl className="grid grid-cols-2 gap-2 text-sm border rounded p-3">
              <dt className="text-gray-500">Plate</dt><dd className="font-medium">{vehicle.plate_number}</dd>
              <dt className="text-gray-500">Make / Model</dt><dd>{vehicle.make} {vehicle.model}</dd>
              <dt className="text-gray-500">Year</dt><dd>{vehicle.year}</dd>
              <dt className="text-gray-500">Color</dt><dd>{vehicle.color}</dd>
              <dt className="text-gray-500">Seats</dt><dd>{vehicle.seat_count}</dd>
              <dt className="text-gray-500">Status</dt>
              <dd>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  vehicle.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                }`}>
                  {vehicle.is_active ? "Active" : "Inactive"}
                </span>
              </dd>
              <dt className="text-gray-500">Registered</dt><dd>{new Date(vehicle.registered_at).toLocaleString()}</dd>
            </dl>
          )}
        </section>
      )}

      {profile.role === "driver" && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Rides ({rides.length})</h2>
          {rides.length === 0 ? (
            <p className="text-sm text-gray-400">No rides yet.</p>
          ) : (
            <ul className="text-sm divide-y border rounded">
              {rides.map((r) => (
                <li key={r.ride_id} className="flex items-center justify-between px-3 py-2">
                  <span className="capitalize">{r.status}</span>
                  <span className="text-gray-500">{new Date(r.created_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {profile.role === "passenger" && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Bookings ({bookings.length})</h2>
          {bookings.length === 0 ? (
            <p className="text-sm text-gray-400">No bookings yet.</p>
          ) : (
            <ul className="text-sm divide-y border rounded">
              {bookings.map((b) => (
                <li key={b.booking_id} className="flex items-center justify-between px-3 py-2">
                  <span className="capitalize">{b.status}</span>
                  <span className="text-gray-500">{new Date(b.created_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">
          Ratings received
          {ratings_received.rating_count > 0 && (
            <span className="text-gray-500 font-normal"> — avg {ratings_received.rating_avg.toFixed(2)} ({ratings_received.rating_count})</span>
          )}
        </h2>
        {ratings_received.items.length === 0 ? (
          <p className="text-sm text-gray-400">No ratings yet.</p>
        ) : (
          <ul className="text-sm divide-y border rounded">
            {ratings_received.items.map((r, i) => (
              <li key={i} className="px-3 py-2">
                <div className="flex items-center justify-between">
                  <span>{"★".repeat(r.stars)}{"☆".repeat(5 - r.stars)}</span>
                  <span className="text-gray-500">{new Date(r.created_at).toLocaleString()}</span>
                </div>
                {r.comment && <p className="text-gray-600 mt-1">{r.comment}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Reports filed by this user ({reports.filed_by_user.length})</h2>
        {reports.filed_by_user.length === 0 ? (
          <p className="text-sm text-gray-400">None.</p>
        ) : (
          <ul className="text-sm divide-y border rounded">
            {reports.filed_by_user.map((r) => (
              <li key={r.report_id} className="flex items-center justify-between px-3 py-2">
                <span className="capitalize">{r.status.replace(/_/g, " ")}</span>
                <span className="text-gray-500">{new Date(r.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Reports filed against this user ({reports.filed_against_user.length})</h2>
        {reports.filed_against_user.length === 0 ? (
          <p className="text-sm text-gray-400">None.</p>
        ) : (
          <ul className="text-sm divide-y border rounded">
            {reports.filed_against_user.map((r) => (
              <li key={r.report_id} className="flex items-center justify-between px-3 py-2">
                <span className="capitalize">{r.status.replace(/_/g, " ")}</span>
                <span className="text-gray-500">{new Date(r.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {wallet && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Wallet</h2>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-gray-500">Balance</dt><dd>{wallet.balance_egp} EGP</dd>
            <dt className="text-gray-500">Available</dt><dd>{wallet.available_egp} EGP</dd>
          </dl>
          {wallet.recent_ledger.length > 0 && (
            <ul className="text-sm divide-y border rounded">
              {wallet.recent_ledger.map((e) => (
                <li key={e.id} className="flex items-center justify-between px-3 py-2">
                  <span>{e.type.replace(/_/g, " ")}</span>
                  <span>{e.amount_egp} EGP</span>
                  <span className="text-gray-500">{new Date(e.created_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}
