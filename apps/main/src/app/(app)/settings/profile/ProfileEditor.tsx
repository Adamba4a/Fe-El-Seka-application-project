"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { updateMe, uploadPhoto } from "@/lib/api/profiles";
import { updateMyVehicle, requestVehicleUpdate } from "@/lib/api/vehicles";
import { switchLocale } from "@/lib/i18n/switch-locale";
import { PasswordSettings } from "./PasswordSettings";
import type { Locale, Profile, Vehicle, VehicleUpdateRequestRecord } from "@fe-el-seka/shared";

const currentYear = new Date().getFullYear();

const inputClass =
  "bg-dash-bg border border-transparent rounded-xl px-2 py-1 text-body-sm text-right text-dash-navy outline-none focus:border-dash-primary transition-colors";

// ─── Quick edit: color + seat_count ──────────────────────────────────────────

function QuickEditForm({ vehicle, token, onSaved, onClose }: {
  vehicle: Vehicle;
  token: string;
  onSaved: (v: Vehicle) => void;
  onClose: () => void;
}) {
  const t = useTranslations("settings.profile.editor.vehicle");
  const tc = useTranslations("common");
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
      setError(err?.detail?.message ?? err?.message ?? t("errors.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3 pt-1">
      <Field label={t("colorLabel")}>
        <input value={color} onChange={(e) => setColor(e.target.value)} className={`w-32 ${inputClass}`} />
      </Field>
      <Field label={t("seatsLabel")}>
        <input type="number" min={2} max={7} value={seatCount} onChange={(e) => setSeatCount(e.target.value)}
          className={`w-16 ${inputClass}`} />
      </Field>
      {error && <p className="text-caption text-content-destructive">{error}</p>}
      <div className="flex gap-2 pt-1">
        <button onClick={onClose}
          className="flex-1 border border-dash-border rounded-xl py-2 text-body-sm text-dash-text-muted hover:bg-dash-bg transition-colors">
          {tc("cancel")}
        </button>
        <button onClick={handleSave} disabled={saving}
          className="flex-1 bg-dash-primary hover:opacity-90 text-white rounded-xl py-2 text-body-sm font-medium disabled:opacity-50 transition-opacity">
          {saving ? tc("saving") : tc("save")}
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
  const t = useTranslations("settings.profile.editor.vehicle");
  const tc = useTranslations("common");
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
      setError(err?.detail?.message ?? err?.message ?? t("errors.submitFailed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3 pt-1">
      <p className="text-caption text-status-in-progress bg-status-in-progress-bg border border-dash-border rounded-xl p-2">
        {t("reviewRequiredNotice")}
      </p>
      <Field label={t("plateNumberLabel")}>
        <input value={plate} onChange={(e) => setPlate(e.target.value)} className={`w-36 ${inputClass}`} />
      </Field>
      <Field label={t("makeLabel")}>
        <input value={make} onChange={(e) => setMake(e.target.value)} className={`w-32 ${inputClass}`} />
      </Field>
      <Field label={t("modelLabel")}>
        <input value={model} onChange={(e) => setModel(e.target.value)} className={`w-32 ${inputClass}`} />
      </Field>
      <Field label={t("yearLabel")}>
        <input type="number" min={2000} max={currentYear + 1} value={year} onChange={(e) => setYear(e.target.value)}
          className={`w-20 ${inputClass}`} />
      </Field>
      {error && <p className="text-caption text-content-destructive">{error}</p>}
      <div className="flex gap-2 pt-1">
        <button onClick={onClose}
          className="flex-1 border border-dash-border rounded-xl py-2 text-body-sm text-dash-text-muted hover:bg-dash-bg transition-colors">
          {tc("cancel")}
        </button>
        <button onClick={handleSubmit} disabled={saving}
          className="flex-1 bg-dash-primary hover:opacity-90 text-white rounded-xl py-2 text-body-sm font-medium disabled:opacity-50 transition-opacity">
          {saving ? t("submitting") : t("submitForReview")}
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
  const t = useTranslations("settings.profile.editor.vehicle");
  const tc = useTranslations("common");
  const [editMode, setEditMode] = useState<"none" | "quick" | "structural">("none");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-bold text-dash-navy">{t("heading")}</h2>
        {editMode === "none" && (
          <button onClick={() => setEditMode("quick")} className="text-body-sm text-dash-primary font-semibold hover:underline">{tc("edit")}</button>
        )}
      </div>

      <div className="bg-dash-surface rounded-2xl shadow-sm p-5 space-y-2 text-body-sm">
        <Row label={t("plateLabel")} value={initialVehicle.plate_number} />
        <Row label={t("makeLabel")} value={initialVehicle.make} />
        <Row label={t("modelLabel")} value={initialVehicle.model} />
        <Row label={t("yearLabel")} value={String(initialVehicle.year)} />
        <Row label={t("colorLabel")} value={initialVehicle.color} />
        <Row label={t("seatsLabel")} value={String(initialVehicle.seat_count)} />

        {initialPending && editMode === "none" && (
          <div className="mt-2 p-2 bg-status-in-progress-bg border border-dash-border rounded-xl text-caption text-status-in-progress space-y-1">
            <p className="font-semibold">{t("pendingReviewNotice")}</p>
            {initialPending.plate_number && <p>{t("pendingPlate", { value: initialPending.plate_number })}</p>}
            {initialPending.make && <p>{t("pendingMake", { value: initialPending.make })}</p>}
            {initialPending.model && <p>{t("pendingModel", { value: initialPending.model })}</p>}
            {initialPending.year && <p>{t("pendingYear", { value: initialPending.year })}</p>}
          </div>
        )}

        {editMode === "quick" && (
          <>
            <QuickEditForm vehicle={initialVehicle} token={token} onSaved={onVehicleSaved} onClose={() => setEditMode("none")} />
            {!initialPending && (
              <button onClick={() => setEditMode("structural")}
                className="w-full text-caption text-status-in-progress border border-dash-border rounded-xl py-1.5 hover:bg-status-in-progress-bg mt-1 transition-colors">
                {t("changeStructural")}
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
      <span className="text-dash-text-muted">{label}</span>
      <span className="font-medium text-dash-navy">{value}</span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-dash-text-muted">{label}</span>
      {children}
    </div>
  );
}

// ─── Language section ─────────────────────────────────────────────────────────

function LanguageSection({ accessToken }: { accessToken: string }) {
  const t = useTranslations("settings.profile.editor.language");
  const currentLocale = useLocale() as Locale;
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = async (locale: Locale) => {
    if (locale === currentLocale || saving) return;
    setSaving(true);
    setError(null);
    try {
      await switchLocale(locale, accessToken);
      router.refresh();
    } catch {
      setError(t("errors.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <h2 className="font-bold text-dash-navy">{t("heading")}</h2>
      <div className="flex gap-2 bg-dash-surface rounded-2xl shadow-sm p-1.5">
        {(["en", "ar"] as const).map((locale) => (
          <button
            key={locale}
            type="button"
            onClick={() => handleSelect(locale)}
            disabled={saving}
            aria-pressed={currentLocale === locale}
            className={`flex-1 rounded-xl py-2 text-body-sm font-semibold transition-colors disabled:opacity-50 ${
              currentLocale === locale
                ? "bg-dash-primary text-content-inverse"
                : "text-dash-text-muted hover:bg-dash-bg"
            }`}
          >
            {t(locale === "en" ? "english" : "arabic")}
          </button>
        ))}
      </div>
      {error && <p className="text-caption text-content-destructive">{error}</p>}
    </div>
  );
}

// ─── Rating summary ───────────────────────────────────────────────────────────

function RatingSummary({ ratingAvg, ratingCount }: { ratingAvg: number | null; ratingCount: number }) {
  const t = useTranslations("settings.profile.editor.rating");
  return (
    <a
      href="/ratings"
      className="bg-dash-surface rounded-2xl shadow-sm p-5 flex items-center justify-between hover:opacity-90 transition-opacity"
    >
      <span className="text-body-sm text-dash-navy">{t("label")}</span>
      <span className="flex items-center gap-2">
        {ratingCount === 0 || ratingAvg === null ? (
          <span className="text-body-sm italic text-dash-text-muted">{t("notRatedYet")}</span>
        ) : (
          <span className="inline-flex items-center gap-1 text-body-sm font-semibold text-amber-600">
            <span aria-hidden="true">★</span>
            {ratingAvg.toFixed(1)}
            <span className="text-dash-text-muted font-normal">
              ({t("count", { count: ratingCount })})
            </span>
          </span>
        )}
        <span className="text-dash-text-muted rtl:rotate-180" aria-hidden="true">›</span>
      </span>
    </a>
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
  const t = useTranslations("settings.profile.editor");
  const [vehicle, setVehicle] = useState(initialVehicle);
  const [pendingUpdate, setPendingUpdate] = useState(initialPendingUpdate);
  const [saved, setSaved] = useState(false);

  const handleProfileSubmit = async (
    { display_name, phone_number }: { display_name: string; phone_number?: string },
    photo: File | null,
  ) => {
    await updateMe(accessToken, { display_name, phone_number });
    if (photo) await uploadPhoto(accessToken, photo);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <main className="max-w-sm mx-auto py-4 space-y-6">
      <div className="flex items-center gap-3">
        <a href={initialProfile.role === "passenger" ? "/search" : "/rides"} className="text-dash-navy hover:opacity-70 text-lg leading-none">
          <span className="inline-block rtl:rotate-180">←</span>
        </a>
        <h1 className="text-h3 font-bold text-dash-navy">{t("heading")}</h1>
      </div>
      {saved && <p className="text-body-sm text-status-completed">{t("saved")}</p>}
      <RatingSummary ratingAvg={initialProfile.rating_avg} ratingCount={initialProfile.rating_count} />
      <ProfileForm
        defaultValues={{
          display_name: initialProfile.display_name,
          profile_photo_url: initialProfile.profile_photo_url,
          phone_number: initialProfile.phone_number,
        }}
        onSubmit={handleProfileSubmit}
        submitLabel={t("saveChanges")}
        showPhone
        photoRequired
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

      <LanguageSection accessToken={accessToken} />

      <PasswordSettings accessToken={accessToken} />

      <div className="pt-2">
        <a
          href="/signout"
          className="w-full flex items-center justify-center py-3 bg-dash-surface shadow-sm rounded-2xl text-body-sm text-content-destructive font-semibold hover:opacity-80 transition-opacity"
        >
          {t("signOut")}
        </a>
      </div>
    </main>
  );
}
