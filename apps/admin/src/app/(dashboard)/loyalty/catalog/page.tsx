"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import {
  getCatalog,
  createVoucher,
  updateCatalogEntry,
  retireCatalogEntry,
  type AdminLoyaltyCatalogEntry,
} from "@/lib/api/admin-loyalty";

const sb = createAdminBrowserClient();

const SYSTEM_TYPES = ["free_ride", "discount", "car_maintenance"] as const;

interface EditState {
  title: string;
  description: string;
  point_cost: string;
  fulfillment_mode: "instant" | "manual";
  loyalty_free_ride_max_fare_egp: string;
  loyalty_discount_percentage: string;
}

const EMPTY_EDIT: EditState = {
  title: "",
  description: "",
  point_cost: "",
  fulfillment_mode: "instant",
  loyalty_free_ride_max_fare_egp: "",
  loyalty_discount_percentage: "",
};

export default function LoyaltyCatalogPage() {
  const [items, setItems] = useState<AdminLoyaltyCatalogEntry[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [edit, setEdit] = useState<EditState>(EMPTY_EDIT);
  const [savingId, setSavingId] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: "",
    description: "",
    audience: "both" as "passenger" | "driver" | "both",
    point_cost: "",
    fulfillment_mode: "instant" as "instant" | "manual",
  });

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  async function load() {
    try {
      const token = await getToken();
      const res = await getCatalog(token);
      setItems(res.items);
    } catch {
      setError("Failed to load loyalty catalog.");
    }
  }

  useEffect(() => {
    setError("");
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startEdit(entry: AdminLoyaltyCatalogEntry) {
    setEditingId(entry.id);
    setEdit({
      title: entry.title,
      description: entry.description,
      point_cost: String(entry.point_cost),
      fulfillment_mode: entry.fulfillment_mode as "instant" | "manual",
      loyalty_free_ride_max_fare_egp: "",
      loyalty_discount_percentage: "",
    });
    setError("");
  }

  function cancelEdit() {
    setEditingId(null);
    setEdit(EMPTY_EDIT);
  }

  async function saveEdit(entry: AdminLoyaltyCatalogEntry) {
    const isSystem = (SYSTEM_TYPES as readonly string[]).includes(entry.type);
    setSavingId(entry.id);
    setError("");
    try {
      const token = await getToken();
      const pointCost = Number(edit.point_cost);
      if (!Number.isFinite(pointCost) || pointCost <= 0) {
        setError("Point cost must be a positive number.");
        setSavingId(null);
        return;
      }
      const payload: Record<string, unknown> = { point_cost: pointCost };
      if (!isSystem) {
        payload.title = edit.title;
        payload.description = edit.description;
        payload.fulfillment_mode = edit.fulfillment_mode;
      } else if (entry.type === "free_ride" && edit.loyalty_free_ride_max_fare_egp.trim()) {
        payload.loyalty_free_ride_max_fare_egp = edit.loyalty_free_ride_max_fare_egp.trim();
      } else if (entry.type === "discount" && edit.loyalty_discount_percentage.trim()) {
        payload.loyalty_discount_percentage = Number(edit.loyalty_discount_percentage.trim());
      }
      await updateCatalogEntry(token, entry.id, payload);
      setNotice(`Updated "${entry.title}".`);
      cancelEdit();
      await load();
    } catch {
      setError("Failed to update catalog entry.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleRetire(entry: AdminLoyaltyCatalogEntry) {
    if (!confirm(`Retire "${entry.title}"? It will no longer be offered for redemption.`)) return;
    setSavingId(entry.id);
    setError("");
    try {
      const token = await getToken();
      await retireCatalogEntry(token, entry.id);
      setNotice(`Retired "${entry.title}".`);
      await load();
    } catch {
      setError("Failed to retire catalog entry.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleReactivate(entry: AdminLoyaltyCatalogEntry) {
    setSavingId(entry.id);
    setError("");
    try {
      const token = await getToken();
      await updateCatalogEntry(token, entry.id, { active: true });
      setNotice(`Reactivated "${entry.title}".`);
      await load();
    } catch {
      setError("Failed to reactivate catalog entry.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleCreate() {
    setError("");
    const pointCost = Number(createForm.point_cost);
    if (!createForm.title.trim() || !createForm.description.trim() || !Number.isFinite(pointCost) || pointCost <= 0) {
      setError("Title, description, and a positive point cost are required.");
      return;
    }
    setCreating(true);
    try {
      const token = await getToken();
      await createVoucher(token, {
        title: createForm.title.trim(),
        description: createForm.description.trim(),
        audience: createForm.audience,
        point_cost: pointCost,
        fulfillment_mode: createForm.fulfillment_mode,
      });
      setNotice(`Created voucher "${createForm.title.trim()}".`);
      setCreateForm({ title: "", description: "", audience: "both", point_cost: "", fulfillment_mode: "instant" });
      setShowCreate(false);
      await load();
    } catch {
      setError("Failed to create voucher.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/loyalty/queue" className="text-sm text-blue-600 hover:underline">
          ← Loyalty Queue
        </Link>
        <h1 className="text-2xl font-semibold">Loyalty Reward Catalog</h1>
      </div>

      {notice && (
        <div className="rounded border border-green-200 bg-green-50 text-green-800 text-sm p-3">{notice}</div>
      )}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="text-sm text-blue-600 hover:underline"
        >
          {showCreate ? "Cancel" : "+ Add voucher"}
        </button>
      </div>

      {showCreate && (
        <div className="border rounded p-4 space-y-3 max-w-lg">
          <h2 className="font-medium text-sm">New voucher</h2>
          <input
            className="w-full border rounded px-2 py-1 text-sm"
            placeholder="Title"
            value={createForm.title}
            onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
          />
          <textarea
            className="w-full border rounded px-2 py-1 text-sm"
            placeholder="Description"
            value={createForm.description}
            onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
          />
          <div className="flex gap-3">
            <select
              className="border rounded px-2 py-1 text-sm"
              value={createForm.audience}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, audience: e.target.value as "passenger" | "driver" | "both" }))
              }
            >
              <option value="both">Both</option>
              <option value="passenger">Passenger</option>
              <option value="driver">Driver</option>
            </select>
            <input
              className="border rounded px-2 py-1 text-sm w-32"
              placeholder="Point cost"
              type="number"
              min={1}
              value={createForm.point_cost}
              onChange={(e) => setCreateForm((f) => ({ ...f, point_cost: e.target.value }))}
            />
            <select
              className="border rounded px-2 py-1 text-sm"
              value={createForm.fulfillment_mode}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, fulfillment_mode: e.target.value as "instant" | "manual" }))
              }
            >
              <option value="instant">Instant</option>
              <option value="manual">Manual</option>
            </select>
          </div>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="text-sm bg-gray-900 text-white rounded px-3 py-1.5 disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create voucher"}
          </button>
        </div>
      )}

      {items.length === 0 ? (
        <p className="text-gray-400 text-sm py-8 text-center">No catalog entries</p>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="pb-2 pr-4 font-medium">Type</th>
              <th className="pb-2 pr-4 font-medium">Title</th>
              <th className="pb-2 pr-4 font-medium">Description</th>
              <th className="pb-2 pr-4 font-medium">Audience</th>
              <th className="pb-2 pr-4 font-medium">Points</th>
              <th className="pb-2 pr-4 font-medium">Mode</th>
              <th className="pb-2 pr-4 font-medium">Active</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((entry) => {
              const isSystem = (SYSTEM_TYPES as readonly string[]).includes(entry.type);
              const isEditing = editingId === entry.id;
              return (
                <tr key={entry.id} className="border-b align-top">
                  <td className="py-3 pr-4 capitalize">{entry.type.replace("_", " ")}</td>
                  {isEditing ? (
                    <>
                      <td className="py-3 pr-4">
                        {isSystem ? (
                          entry.title
                        ) : (
                          <input
                            className="border rounded px-2 py-1 text-sm w-full"
                            value={edit.title}
                            onChange={(e) => setEdit((s) => ({ ...s, title: e.target.value }))}
                          />
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        {isSystem ? (
                          entry.description
                        ) : (
                          <textarea
                            className="border rounded px-2 py-1 text-sm w-full"
                            value={edit.description}
                            onChange={(e) => setEdit((s) => ({ ...s, description: e.target.value }))}
                          />
                        )}
                      </td>
                      <td className="py-3 pr-4 capitalize">{entry.audience}</td>
                      <td className="py-3 pr-4">
                        <input
                          className="border rounded px-2 py-1 text-sm w-20"
                          type="number"
                          min={1}
                          value={edit.point_cost}
                          onChange={(e) => setEdit((s) => ({ ...s, point_cost: e.target.value }))}
                        />
                        {entry.type === "free_ride" && (
                          <input
                            className="border rounded px-2 py-1 text-sm w-28 mt-1 block"
                            placeholder="Max fare EGP"
                            value={edit.loyalty_free_ride_max_fare_egp}
                            onChange={(e) =>
                              setEdit((s) => ({ ...s, loyalty_free_ride_max_fare_egp: e.target.value }))
                            }
                          />
                        )}
                        {entry.type === "discount" && (
                          <input
                            className="border rounded px-2 py-1 text-sm w-28 mt-1 block"
                            placeholder="Discount %"
                            type="number"
                            min={0}
                            max={100}
                            value={edit.loyalty_discount_percentage}
                            onChange={(e) =>
                              setEdit((s) => ({ ...s, loyalty_discount_percentage: e.target.value }))
                            }
                          />
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        {isSystem ? (
                          entry.fulfillment_mode
                        ) : (
                          <select
                            className="border rounded px-2 py-1 text-sm"
                            value={edit.fulfillment_mode}
                            onChange={(e) =>
                              setEdit((s) => ({ ...s, fulfillment_mode: e.target.value as "instant" | "manual" }))
                            }
                          >
                            <option value="instant">Instant</option>
                            <option value="manual">Manual</option>
                          </select>
                        )}
                      </td>
                      <td className="py-3 pr-4">{entry.active ? "Yes" : "No"}</td>
                      <td className="py-3 space-x-3">
                        <button
                          onClick={() => saveEdit(entry)}
                          disabled={savingId === entry.id}
                          className="text-green-600 hover:underline disabled:text-gray-400"
                        >
                          Save
                        </button>
                        <button onClick={cancelEdit} className="text-gray-500 hover:underline">
                          Cancel
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="py-3 pr-4">{entry.title}</td>
                      <td className="py-3 pr-4 text-gray-500 max-w-xs">{entry.description}</td>
                      <td className="py-3 pr-4 capitalize">{entry.audience}</td>
                      <td className="py-3 pr-4">{entry.point_cost}</td>
                      <td className="py-3 pr-4 capitalize">{entry.fulfillment_mode}</td>
                      <td className="py-3 pr-4">{entry.active ? "Yes" : "No"}</td>
                      <td className="py-3 space-x-3">
                        <button
                          onClick={() => startEdit(entry)}
                          disabled={savingId === entry.id}
                          className="text-blue-600 hover:underline disabled:text-gray-400"
                        >
                          Edit
                        </button>
                        {entry.active ? (
                          !isSystem && (
                            <button
                              onClick={() => handleRetire(entry)}
                              disabled={savingId === entry.id}
                              className="text-red-600 hover:underline disabled:text-gray-400"
                            >
                              Retire
                            </button>
                          )
                        ) : (
                          <button
                            onClick={() => handleReactivate(entry)}
                            disabled={savingId === entry.id}
                            className="text-green-600 hover:underline disabled:text-gray-400"
                          >
                            Reactivate
                          </button>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}
