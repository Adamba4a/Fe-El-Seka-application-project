"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import {
  getRecurringDefinition,
  editRecurringDefinition,
  endRecurringDefinition,
  overrideRecurringOccurrence,
  localTimeToUtcTime,
  utcTimeToLocalTime,
} from "@/lib/api/recurring-rides";
import { RideCard } from "@/components/rides/RideCard";
import { BottomSheet, Spinner } from "@/components";
import { formatCurrency } from "@fe-el-seka/shared";
import type { RecurringRideDefinition, Ride, Locale } from "@fe-el-seka/shared";
import { toIsoWeekday, fromIsoWeekday } from "@/lib/weekdays";
import { getFareEstimate } from "@/lib/api/pricing";

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const;

export default function RecurringRideDetailPage() {
  const t = useTranslations("driver.recurring");
  const locale = useLocale() as Locale;
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [definition, setDefinition] = useState<RecurringRideDefinition | null>(null);
  const [instances, setInstances] = useState<Ride[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [editTime, setEditTime] = useState("");
  const [editWeekdays, setEditWeekdays] = useState<number[]>([]);
  const [editSeats, setEditSeats] = useState(1);
  const [editPrice, setEditPrice] = useState(0);
  const [editFairPrice, setEditFairPrice] = useState<number | null>(null);
  const [editMaxPrice, setEditMaxPrice] = useState<number | null>(null);
  const [editFareLoading, setEditFareLoading] = useState(false);
  const [editFareError, setEditFareError] = useState<string | null>(null);
  const [editNotes, setEditNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  const [isEndConfirmOpen, setIsEndConfirmOpen] = useState(false);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState<string | null>(null);
  const [overrideRide, setOverrideRide] = useState<Ride | null>(null);
  const [overrideOutbound, setOverrideOutbound] = useState("");
  const [overrideReturn, setOverrideReturn] = useState("");
  const [overrideError, setOverrideError] = useState<string | null>(null);
  const [overriding, setOverriding] = useState(false);

  const load = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      const res = await getRecurringDefinition(session.access_token, id);
      setDefinition(res.definition);
      setInstances(res.instances);
      setEditTime(utcTimeToLocalTime(res.definition.departure_time.substring(0, 5)));
      setEditWeekdays(res.definition.weekdays.map(fromIsoWeekday));
      setEditSeats(res.definition.total_seats);
      setEditPrice(Number(res.definition.price_per_seat));
      setEditNotes(res.definition.notes ?? "");
    } catch (err: any) {
      setFetchError(err?.message ?? t("loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!definition || !isEditing) return;
    let cancelled = false;
    setEditFareLoading(true);
    setEditFareError(null);
    getFareEstimate(definition.origin.coordinates, definition.destination.coordinates, editSeats)
      .then((estimate) => {
        if (cancelled) return;
        setEditFairPrice(estimate.per_seat_price_egp);
        setEditMaxPrice(estimate.max_price_per_seat_egp);
        setEditPrice((price) => Math.min(estimate.max_price_per_seat_egp, Math.max(estimate.per_seat_price_egp, price)));
      })
      .catch(() => {
        if (!cancelled) setEditFareError(t("fareEstimateFailed"));
      })
      .finally(() => {
        if (!cancelled) setEditFareLoading(false);
      });
    return () => { cancelled = true; };
  }, [definition, editSeats, isEditing, t]);

  const handleSave = async () => {
    if (editFairPrice === null || editMaxPrice === null || editPrice < editFairPrice || editPrice > editMaxPrice) {
      setSaveError(t("fareEstimatePending"));
      return;
    }
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      const res = await editRecurringDefinition(session.access_token, id, {
        departure_time: localTimeToUtcTime(editTime),
        weekdays: editWeekdays.map(toIsoWeekday),
        total_seats: editSeats,
        price_per_seat: editPrice,
        notes: editNotes.trim() || undefined,
      });
      setDefinition(res.definition);
      setSaveSuccess(t("editSuccessPrefix", { count: res.updated_instance_count }));
      setIsEditing(false);
    } catch (err: any) {
      const detail = err?.detail ?? err;
      setSaveError(detail?.message ?? t("saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const handleEndSeries = async () => {
    setEnding(true);
    setEndError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      const updated = await endRecurringDefinition(session.access_token, id);
      setDefinition((prev) => (prev ? { ...prev, status: updated.status } : prev));
      setIsEndConfirmOpen(false);
      setIsEditing(false);
    } catch (err: any) {
      setEndError(err?.message ?? t("endSeriesFailed"));
    } finally {
      setEnding(false);
    }
  };

  const toLocalInput = (iso: string) => {
    const value = new Date(iso);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
  };

  const openOverride = (outbound: Ride) => {
    const sibling = instances.find((ride) => ride.round_trip_group_id === outbound.round_trip_group_id && ride.trip_leg === "return");
    if (!sibling) return;
    setOverrideRide(outbound);
    setOverrideOutbound(toLocalInput(outbound.departure_datetime));
    setOverrideReturn(toLocalInput(sibling.departure_datetime));
    setOverrideError(null);
  };

  const saveOverride = async () => {
    if (!overrideRide || !overrideOutbound || !overrideReturn) return;
    setOverriding(true);
    setOverrideError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }
      await overrideRecurringOccurrence(session.access_token, id, overrideRide.departure_datetime.slice(0, 10), {
        outbound_departure_datetime: new Date(overrideOutbound).toISOString(),
        return_departure_datetime: new Date(overrideReturn).toISOString(),
      });
      setOverrideRide(null);
      await load();
    } catch (err: any) {
      setOverrideError(err?.message ?? "Unable to update this occurrence.");
    } finally {
      setOverriding(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-surface-bg rounded-xl animate-pulse" />)}
      </div>
    );
  }

  if (fetchError || !definition) {
    return (
      <div className="text-center py-12 space-y-3">
        <p className="text-body-sm text-content-secondary">{fetchError ?? t("notFoundTitle")}</p>
        <Link href="/rides/recurring" className="text-body-sm text-brand-primary underline">{t("backToList")}</Link>
      </div>
    );
  }

  const inputClass = "w-full border border-border-default rounded-xl px-3 py-2 text-body-sm outline-none focus:border-border-focus transition-colors";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/rides/recurring" className="text-content-muted hover:text-content-secondary">
          <span className="inline-block rtl:rotate-180">←</span>
        </Link>
        <h1 className="text-h3 text-content-primary">{t("detailHeading")}</h1>
      </div>

      <div className="bg-surface-card border border-border-default rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span
            className={`inline-flex items-center rounded-full text-xs font-medium px-2 py-0.5 ${
              definition.status === "active"
                ? "bg-green-500/10 text-green-700"
                : "bg-surface-bg text-content-muted"
            }`}
          >
            {t(definition.status === "active" ? "statusActive" : "statusEnded")}
          </span>
          {definition.status === "active" && !isEditing && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="rounded-xl bg-dash-primary px-4 py-2 text-body-sm font-semibold text-content-inverse hover:opacity-90 transition-opacity"
              >
                {t("editButton")}
              </button>
              <button
                type="button"
                onClick={() => setIsEndConfirmOpen(true)}
                className="rounded-xl border border-border-default px-4 py-2 text-body-sm font-semibold text-content-destructive hover:bg-status-cancelled-bg transition-colors"
              >
                {t("endSeriesButton")}
              </button>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">{t("fromLabel")}</p>
            <p className="text-body-sm font-medium text-content-primary">{definition.origin.address}</p>
          </div>
          <div>
            <p className="text-caption text-content-muted uppercase tracking-wide">{t("toLabel")}</p>
            <p className="text-body-sm font-medium text-content-primary">{definition.destination.address}</p>
          </div>
        </div>

        {saveSuccess && (
          <p className="text-body-sm text-green-700 bg-green-500/10 rounded-xl px-3 py-2">{saveSuccess}</p>
        )}

        {!isEditing ? (
          <>
            <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border-default">
              <div className="text-center">
                <p className="text-lg font-bold text-content-primary">{utcTimeToLocalTime(definition.departure_time.substring(0, 5))}</p>
                <p className="text-caption text-content-muted">{t("timeLabel")}</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-content-primary">{definition.total_seats}</p>
                <p className="text-caption text-content-muted">{t("seatsLabel")}</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-content-primary">
                  {formatCurrency(Number(definition.price_per_seat), locale)}
                </p>
                <p className="text-caption text-content-muted">{t("perSeatSuffix")}</p>
              </div>
            </div>

            <div>
              <p className="text-caption text-content-muted uppercase tracking-wide">{t("weekdaysLabel")}</p>
              <p className="text-body-sm font-medium text-content-primary">
                {definition.weekdays.map((d) => t(`weekdayShort.${fromIsoWeekday(d)}`)).join(", ")}
              </p>
            </div>

            {(definition.is_women_only || definition.journey_type === "round_trip") && (
              <div className="flex flex-wrap gap-2">
                {definition.is_women_only && <span className="rounded-full bg-pink-100 px-2 py-1 text-xs font-medium text-pink-700">{t("womenOnly")}</span>}
                {definition.journey_type === "round_trip" && <span className="rounded-full bg-brand-primary/10 px-2 py-1 text-xs font-medium text-brand-primary">{t("roundTrip")}</span>}
              </div>
            )}

            {definition.journey_type === "round_trip" && definition.return_departure_time && (
              <div className="grid grid-cols-3 gap-3 rounded-xl bg-surface-bg p-3 text-center">
                <div><p className="font-semibold text-content-primary">{utcTimeToLocalTime(definition.return_departure_time.substring(0, 5))}</p><p className="text-caption text-content-muted">{t("returnTimeLabel")}</p></div>
                <div><p className="font-semibold text-content-primary">{definition.return_total_seats}</p><p className="text-caption text-content-muted">{t("returnSeatsLabel")}</p></div>
                <div><p className="font-semibold text-content-primary">{formatCurrency(Number(definition.return_price_per_seat), locale)}</p><p className="text-caption text-content-muted">{t("returnPriceLabel")}</p></div>
              </div>
            )}

            {definition.notes && (
              <p className="text-body-sm text-content-secondary bg-surface-bg rounded-xl px-3 py-2">
                {definition.notes}
              </p>
            )}
          </>
        ) : (
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="block text-label text-content-secondary">{t("timeLabel")}</label>
              <input
                type="time"
                value={editTime}
                onChange={(e) => setEditTime(e.target.value)}
                className={inputClass}
              />
            </div>

            <div className="space-y-1">
              <label className="block text-label text-content-secondary">{t("weekdaysLabel")}</label>
              <div className="flex gap-1.5 flex-wrap">
                {WEEKDAYS.map((day) => {
                  const selected = editWeekdays.includes(day);
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() =>
                        setEditWeekdays((prev) =>
                          selected ? prev.filter((d) => d !== day) : [...prev, day].sort()
                        )
                      }
                      className={`w-10 h-10 rounded-full text-body-sm font-medium transition-colors ${
                        selected
                          ? "bg-dash-primary text-content-inverse"
                          : "bg-surface-bg text-content-secondary hover:bg-border-default"
                      }`}
                    >
                      {t(`weekdayShort.${day}`)}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-1">
              <label className="block text-label text-content-secondary">{t("seatsLabel")}</label>
              <input
                type="number"
                min={1}
                max={7}
                value={editSeats}
                onChange={(e) => setEditSeats(Number(e.target.value))}
                className={inputClass}
              />
            </div>

            <div className="space-y-1">
              <label className="block text-label text-content-secondary">{t("priceLabel")}</label>
              {editFareLoading && <p className="flex items-center gap-2 text-body-sm text-content-muted"><Spinner /> {t("priceEstimating")}</p>}
              {editFareError && <p className="text-body-sm text-content-destructive">{editFareError}</p>}
              {editFairPrice !== null && editMaxPrice !== null && (
                <div className="space-y-2 rounded-xl bg-surface-bg px-3 py-3">
                  <div className="flex justify-between text-caption text-content-muted"><span>{t("fairPriceLabel")}</span><span>{formatCurrency(editFairPrice, locale)}</span></div>
                  {editFairPrice < editMaxPrice && <input type="range" min={editFairPrice} max={editMaxPrice} step={1} value={editPrice} onChange={(e) => setEditPrice(Number(e.target.value))} className="w-full accent-dash-primary" />}
                  <div className="flex justify-between"><span className="text-label text-content-primary">{t("selectedPriceLabel")}</span><span className="text-heading-sm font-medium text-content-primary">{formatCurrency(editPrice, locale)}</span></div>
                  <div className="flex justify-between text-caption text-content-muted"><span>{t("maxPriceLabel")}</span><span>{formatCurrency(editMaxPrice, locale)}</span></div>
                </div>
              )}
              <p className="text-caption text-content-muted">{t("priceRangeHint")}</p>
            </div>

            <div className="space-y-1">
              <label className="block text-label text-content-secondary">{t("notesLabel")}</label>
              <textarea
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                rows={2}
                className={`${inputClass} resize-none`}
              />
            </div>

            {saveError && <p className="text-body-sm text-content-destructive">{saveError}</p>}

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => {
                  setIsEditing(false);
                  setSaveError(null);
                  setEditTime(utcTimeToLocalTime(definition.departure_time.substring(0, 5)));
                  setEditWeekdays(definition.weekdays.map(fromIsoWeekday));
                  setEditSeats(definition.total_seats);
                  setEditPrice(Number(definition.price_per_seat));
                  setEditNotes(definition.notes ?? "");
                }}
                className="flex-1 py-3 px-4 border border-border-default rounded-xl text-body-sm text-content-secondary font-medium transition-colors"
              >
                {t("cancelEdit")}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-dash-primary text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-opacity"
              >
                {saving && <Spinner />}
                {saving ? t("savingChanges") : t("saveChanges")}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-surface-card border border-border-default rounded-2xl p-5 space-y-4">
        <h2 className="font-semibold text-content-primary">{t("instancesHeading")}</h2>
        {instances.length > 0 && (
          <p className="text-caption text-content-muted">{t("instancesHint")}</p>
        )}
        {instances.length === 0 ? (
          <p className="text-body-sm text-content-muted">{t("noInstancesYet")}</p>
        ) : (
          <div className="space-y-3">
            {instances.map((ride) => (
              <div key={ride.id} className="space-y-2">
                <RideCard ride={ride} href={`/rides/${ride.id}/bookings`} />
                {definition.journey_type === "round_trip" && ride.trip_leg === "outbound" && (
                  <button type="button" onClick={() => openOverride(ride)} className="w-full rounded-xl border border-brand-primary/30 bg-brand-primary/5 px-3 py-2 text-left text-xs font-medium text-dash-primary">
                    {t("adjustOccurrenceTimes")}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <BottomSheet isOpen={overrideRide !== null} onClose={() => setOverrideRide(null)}>
        <div className="space-y-4">
          <h2 className="text-h3 text-content-primary">{t("adjustOccurrenceHeading")}</h2>
          <p className="text-body-sm text-content-muted">{t("adjustOccurrenceHint")}</p>
          <label className="block text-label text-content-secondary">{t("outboundTimeLabel")}<input type="datetime-local" value={overrideOutbound} onChange={(e) => setOverrideOutbound(e.target.value)} className="mt-1 w-full border border-border-default rounded-xl px-3 py-2" /></label>
          <label className="block text-label text-content-secondary">{t("returnTimeLabel")}<input type="datetime-local" value={overrideReturn} onChange={(e) => setOverrideReturn(e.target.value)} className="mt-1 w-full border border-border-default rounded-xl px-3 py-2" /></label>
          {overrideError && <p className="text-caption text-content-destructive">{overrideError}</p>}
          <button type="button" onClick={saveOverride} disabled={overriding} className="w-full py-3 bg-dash-primary text-content-inverse rounded-xl font-medium disabled:opacity-50">{overriding ? t("savingChanges") : t("saveTimes")}</button>
        </div>
      </BottomSheet>

      <BottomSheet isOpen={isEndConfirmOpen} onClose={() => setIsEndConfirmOpen(false)}>
        <div className="space-y-4">
          <h2 className="text-h3 text-content-primary">{t("endSeriesConfirmTitle")}</h2>
          <p className="text-body-sm text-content-muted">{t("endSeriesConfirmBody")}</p>
          {endError && <p className="text-caption text-content-destructive">{endError}</p>}
          <button
            type="button"
            onClick={handleEndSeries}
            disabled={ending}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-surface-destructive text-content-inverse rounded-xl font-medium disabled:opacity-50 transition-colors"
          >
            {ending && <Spinner />}
            {ending ? t("endingSeries") : t("confirmEndSeries")}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}
