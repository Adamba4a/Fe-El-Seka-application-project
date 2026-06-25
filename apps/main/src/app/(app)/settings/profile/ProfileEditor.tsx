"use client";

import { useState } from "react";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { updateMe, uploadPhoto } from "@/lib/api/profiles";
import { updateMyVehicle, requestVehicleUpdate } from "@/lib/api/vehicles";
import type { Profile, Vehicle, VehicleUpdateRequestRecord } from "@fe-el-seka/shared";

const currentYear = new Date().getFullYear();

const inputClass =
  "border border-border-default rounded-xl px-2 py-1 text-body-sm text-right outline-none focus:border-border-focus transition-colors";

// ─── Quick edit: color + seat_count ──────────────────────────────────────────

function QuickEditForm({ vehicle, token, onSaved, onClose }: {
  vehicle: Vehicle;
  token: string;
  onSaved: (v: Vehicle) => void;
  onClose: () => void;
}) {
  const [color, setColor] = useState(vehicle.color);
  const [seatCount, setSeatCount] = useState(String(vehicle.seat_count));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateMyVehicle(token, {
        color: color.trim() || undefined,
        seat_count: seatCount ? Number(seatCount) : undefined,
      });
      onSaved(updated);
      onClose();
    } catch (err: any) {
      setError(err?.detail?.message ?? err?.message ?? "Failed to save.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3 pt-1">
      <Field label="Color">
        <input value={color} onChange={(e) => setColor(e.target.value)} className={`w-32 ${inputClass}`} />
      </Field>
      <Field label="Seats (excl. driver)">
        <input type="number" min={2} max={7} value={seatCount} onChange={(e) => setSeatCount(e.target.value)}
          className={`w-16 ${inputClass}`} />
      </Field>
      {error && <p className="text-caption text-content-destructive">{error}</p>}
      <div className="flex gap-2 pt-1">
        <button onClick={onClose}
          className="flex-1 border border-border-default rounded-xl py-2 text-body-sm text-content-secondary hover:bg-surface-bg transition-colors">
          Cancel
        </button>
        <button onClick={handleSave} disabled={saving}
          className="flex-1 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-2 text-body-sm font-medium disabled:opacity-50 transition-colors">
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

// ─── Structural edit: plate + make + model + year (requires review) ───────────

function StructuralEditForm({ vehicle, token, onSubmitted, onClose }: {
  vehicle: Vehicle;
  token: string;
  onSubmitted: (req: VehicleUpdateRequestRecord) => void;
  onClose: () => void;
}) {
  const [plate, setPlate] = useState(vehicle.plate_number);
  const [make, setMake] = useState(vehicle.make);
  const [model, setModel] = useState(vehicle.model);
  const [year, setYear] = useState(String(vehicle.year));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      const req = await requestVehicleUpdate(token, {
        plate_number: plate.trim() || undefined,
        make: make.trim() || undefined,
        model: model.trim() || undefined,
        year: year ? Number(year) : undefined,
      });
      onSubmitted(req);
      onClose();
    } catch (err: any) {
      setError(err?.detail?.message ?? err?.message ?? "Failed to submit request.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3 pt-1">
      <p className="text-caption text-status-in-progress bg-status-in-progress-bg border border-border-default rounded-xl p-2">
        Changes to plate number, make, model, or year require admin review before taking effect.
      </p>
      <Field label="Plate Number">
        <input value={plate} onChange={(e) => setPlate(e.target.value)} className={`w-36 ${inputClass}`} />
      </Field>
      <Field label="Make">
        <input value={make} onChange={(e) => setMake(e.target.value)} className={`w-32 ${inputClass}`} />
      </Field>
      <Field label="Model">
        <input value={model} onChange={(e) => setModel(e.target.value)} className={`w-32 ${inputClass}`} />
      </Field>
      <Field label="Year">
        <input type="number" min={2000} max={currentYear + 1} value={year} onChange={(e) => setYear(e.target.value)}
          className={`w-20 ${inputClass}`} />
      </Field>
      {error && <p className="text-caption text-content-destructive">{error}</p>}
      <div className="flex gap-2 pt-1">
        <button onClick={onClose}
          className="flex-1 border border-border-default rounded-xl py-2 text-body-sm text-content-secondary hover:bg-surface-bg transition-colors">
          Cancel
        </button>
        <button onClick={handleSubmit} disabled={saving}
          className="flex-1 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse rounded-xl py-2 text-body-sm font-medium disabled:opacity-50 transition-colors">
          {saving ? "Submitting…" : "Submit for Review"}
        </button>
      </div>
    </div>
  );
}

// ─── Vehicle section ──────────────────────────────────────────────────────────

function VehicleSection({ vehicle: initialVehicle, pendingUpdate: initialPending, token, onVehicleSaved, onUpdateRequested }: {
  vehicle: Vehicle;
  pendingUpdate: VehicleUpdateRequestRecord | null;
  token: string;
  onVehicleSaved: (v: Vehicle) => void;
  onUpdateRequested: (req: VehicleUpdateRequestRecord) => void;
}) {
  const [editMode, setEditMode] = useState<"none" | "quick" | "structural">("none");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-content-primary">Vehicle</h2>
        {editMode === "none" && (
          <button onClick={() => setEditMode("quick")} className="text-body-sm text-brand-primary hover:underline">Edit</button>
        )}
      </div>

      <div className="bg-surface-bg rounded-xl p-4 space-y-2 text-body-sm">
        <Row label="Plate" value={initialVehicle.plate_number} />
        <Row label="Make" value={initialVehicle.make} />
        <Row label="Model" value={initialVehicle.model} />
        <Row label="Year" value={String(initialVehicle.year)} />
        <Row label="Color" value={initialVehicle.color} />
        <Row label="Seats (excl. driver)" value={String(initialVehicle.seat_count)} />

        {initialPending && editMode === "none" && (
          <div className="mt-2 p-2 bg-status-in-progress-bg border border-border-default rounded-xl text-caption text-status-in-progress space-y-1">
            <p className="font-semibold">Registration change pending review</p>
            {initialPending.plate_number && <p>Plate: {initialPending.plate_number}</p>}
            {initialPending.make && <p>Make: {initialPending.make}</p>}
            {initialPending.model && <p>Model: {initialPending.model}</p>}
            {initialPending.year && <p>Year: {initialPending.year}</p>}
          </div>
        )}

        {editMode === "quick" && (
          <>
            <QuickEditForm vehicle={initialVehicle} token={token} onSaved={onVehicleSaved} onClose={() => setEditMode("none")} />
            {!initialPending && (
              <button onClick={() => setEditMode("structural")}
                className="w-full text-caption text-status-in-progress border border-border-default rounded-xl py-1.5 hover:bg-status-in-progress-bg mt-1 transition-colors">
                Change plate / make / model / year (requires review)
              </button>
            )}
          </>
        )}

        {editMode === "structural" && (
          <StructuralEditForm
            vehicle={initialVehicle}
            token={token}
            onSubmitted={(req) => { onUpdateRequested(req); setEditMode("none"); }}
            onClose={() => setEditMode("quick")}
          />
        )}
      </div>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-content-muted">{label}</span>
      <span className="font-medium text-content-primary">{value}</span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-content-muted">{label}</span>
      {children}
    </div>
  );
}

// ─── Main editor component ────────────────────────────────────────────────────

export function ProfileEditor({
  initialProfile,
  initialVehicle,
  initialPendingUpdate,
  accessToken,
}: {
  initialProfile: Profile;
  initialVehicle: Vehicle | null;
  initialPendingUpdate: VehicleUpdateRequestRecord | null;
  accessToken: string;
}) {
  const [vehicle, setVehicle] = useState(initialVehicle);
  const [pendingUpdate, setPendingUpdate] = useState(initialPendingUpdate);
  const [saved, setSaved] = useState(false);

  const handleProfileSubmit = async ({ display_name }: { display_name: string }, photo: File | null) => {
    await updateMe(accessToken, { display_name });
    if (photo) await uploadPhoto(accessToken, photo);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <main className="max-w-sm mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <a href={initialProfile.role === "passenger" ? "/search" : "/rides"} className="text-content-muted hover:text-content-secondary text-lg leading-none">←</a>
        <h1 className="text-h3 text-content-primary">Edit Profile</h1>
      </div>
      {saved && <p className="text-body-sm text-status-completed">Profile saved!</p>}
      <ProfileForm
        defaultValues={{ display_name: initialProfile.display_name, profile_photo_url: initialProfile.profile_photo_url }}
        onSubmit={handleProfileSubmit}
        submitLabel="Save Changes"
      />
      {vehicle && (
        <VehicleSection
          vehicle={vehicle}
          pendingUpdate={pendingUpdate}
          token={accessToken}
          onVehicleSaved={setVehicle}
          onUpdateRequested={setPendingUpdate}
        />
      )}

      <div className="pt-4 border-t border-border-default">
        <a
          href="/signout"
          className="w-full flex items-center justify-center py-3 border border-border-default rounded-xl text-body-sm text-content-destructive font-medium hover:bg-status-cancelled-bg transition-colors"
        >
          Sign out
        </a>
      </div>
    </main>
  );
}
