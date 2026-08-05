"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/Spinner";
import { createClient } from "@/lib/supabase/client";

type BookingStatus = "pending" | "confirmed" | "cancelled" | "completed";

interface BookingSummary {
  booking_id: string;
  ride_id: string;
  status: BookingStatus;
  passenger_id: string;
  driver_id: string;
  passenger_display_name?: string;
  driver_display_name?: string;
  driver_avatar_url?: string;
  already_rated: boolean;
}

async function apiFetch(path: string, options?: RequestInit) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg =
      err?.detail?.message ?? err?.detail ?? err?.message ?? `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return res.json();
}

export default function RateReportPage() {
  const t = useTranslations("ratings.rateReport");
  const params = useParams<{ bookingId: string }>();
  const bookingId = params.bookingId;
  const router = useRouter();

  const REPORT_CATEGORIES: { value: string; label: string }[] = [
    { value: "unsafe_driving", label: t("categories.unsafeDriving") },
    { value: "harassment", label: t("categories.harassment") },
    { value: "no_show", label: t("categories.noShow") },
    { value: "fraud_or_scam", label: t("categories.fraudOrScam") },
    { value: "vehicle_mismatch", label: t("categories.vehicleMismatch") },
    { value: "other", label: t("categories.other") },
  ];

  const [booking, setBooking] = useState<BookingSummary | null>(null);
  const [selfId, setSelfId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [ratingState, setRatingState] = useState<"idle" | "submitting" | "done" | "already">("idle");
  const [ratingError, setRatingError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);

  const [category, setCategory] = useState(REPORT_CATEGORIES[0].value);
  const [description, setDescription] = useState("");
  const [reportState, setReportState] = useState<"idle" | "submitting" | "done">("idle");
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        setSelfId(session?.user.id ?? null);
        const data = await apiFetch(`/api/v1/bookings/${bookingId}`);
        setBooking(data);
        if (data.already_rated) setRatingState("already");
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : t("errors.loadFailed"));
      } finally {
        setLoading(false);
      }
    })();
  }, [bookingId]);

  const isDriver = booking !== null && selfId === booking.driver_id;
  const otherPartyId = booking ? (isDriver ? booking.passenger_id : booking.driver_id) : null;
  const otherPartyLabel = booking
    ? isDriver
      ? booking.passenger_display_name ?? t("defaultOtherPartyPassenger")
      : booking.driver_display_name ?? t("defaultOtherPartyDriver")
    : "";

  async function submitRating() {
    if (stars < 1) return;
    setRatingState("submitting");
    setRatingError(null);
    try {
      const res = await apiFetch("/api/v1/ratings", {
        method: "POST",
        body: JSON.stringify({ booking_id: bookingId, stars, comment: comment.trim() || null }),
      });
      setRevealed(res.revealed);
      setRatingState("done");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("errors.ratingFailed");
      if (msg === "You have already rated this booking") {
        setRatingState("already");
      } else {
        setRatingError(msg);
        setRatingState("idle");
      }
    }
  }

  async function submitReport() {
    if (!booking || !otherPartyId || description.trim().length === 0) return;
    setReportState("submitting");
    setReportError(null);
    try {
      await apiFetch("/api/v1/reports", {
        method: "POST",
        body: JSON.stringify({
          ride_id: booking.ride_id,
          booking_id: booking.booking_id,
          reported_user_id: otherPartyId,
          category,
          description: description.trim(),
        }),
      });
      setReportState("done");
    } catch (e: unknown) {
      setReportError(e instanceof Error ? e.message : t("errors.reportFailed"));
      setReportState("idle");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Spinner />
      </div>
    );
  }

  if (error || !booking) {
    return (
      <div className="p-4 text-center text-content-destructive">
        <p>{error ?? t("errors.bookingNotFound")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-content-muted hover:text-content-secondary"
        >
          <span className="inline-block rtl:rotate-180">←</span>
        </button>
        <h1 className="text-xl font-semibold text-content-primary">{t("heading")}</h1>
      </div>

      {booking.status !== "completed" ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-4 text-sm text-content-muted">
          {t("notCompletedNotice")}
        </div>
      ) : (
        <>
          {/* Rate the other party */}
          <div className="rounded-xl border border-border-default bg-surface-card">
            <div className="p-4 space-y-3">
              <p className="font-medium text-content-primary">{t("ratePrefix", { name: otherPartyLabel })}</p>

              {ratingState === "done" ? (
                <p className="text-sm text-green-700">
                  {t("thanksMessage")}{" "}
                  {revealed ? t("revealedNote") : t("notRevealedNote")}
                </p>
              ) : ratingState === "already" ? (
                <p className="text-sm text-content-muted">{t("alreadyRated")}</p>
              ) : (
                <>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setStars(n)}
                        className={`text-2xl leading-none ${n <= stars ? "text-amber-400" : "text-border-default"}`}
                        aria-label={t("starAriaLabel", { count: n })}
                      >
                        ★
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value.slice(0, 500))}
                    placeholder={t("commentPlaceholder")}
                    rows={3}
                    className="w-full rounded-lg border border-border-default bg-surface-bg p-2 text-sm text-content-primary"
                  />
                  <p className="text-xs text-content-muted text-end">{t("charCount500", { count: comment.length })}</p>
                  {ratingError && <p className="text-sm text-content-destructive">{ratingError}</p>}
                  <button
                    type="button"
                    onClick={submitRating}
                    disabled={stars < 1 || ratingState === "submitting"}
                    className="w-full rounded-xl bg-brand-primary hover:bg-brand-primary-hover text-white px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {ratingState === "submitting" && <Spinner />}
                    {t("submitRating")}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Report a concern */}
          <div className="rounded-xl border border-border-default bg-surface-card">
            <div className="p-4 space-y-3">
              <p className="font-medium text-content-primary">{t("reportHeading")}</p>

              {reportState === "done" ? (
                <p className="text-sm text-green-700">{t("reportDoneMessage")}</p>
              ) : (
                <>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full rounded-lg border border-border-default bg-surface-bg p-2 text-sm text-content-primary"
                  >
                    {REPORT_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value.slice(0, 1000))}
                    placeholder={t("descriptionPlaceholder")}
                    rows={4}
                    className="w-full rounded-lg border border-border-default bg-surface-bg p-2 text-sm text-content-primary"
                  />
                  <p className="text-xs text-content-muted text-end">{t("charCount1000", { count: description.length })}</p>
                  {reportError && <p className="text-sm text-content-destructive">{reportError}</p>}
                  <button
                    type="button"
                    onClick={submitReport}
                    disabled={description.trim().length === 0 || reportState === "submitting"}
                    className="w-full rounded-xl border border-border-default text-content-destructive hover:bg-status-cancelled-bg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {reportState === "submitting" && <Spinner />}
                    {t("submitReport")}
                  </button>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
