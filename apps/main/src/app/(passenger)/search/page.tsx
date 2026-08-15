"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { RideSearchForm, type SearchLocation } from "@/components/bookings/RideSearchForm";
import { RideCard, type RideCandidate } from "@/components/bookings/RideCard";
import { BottomSheet } from "@/components";
import { env } from "@/lib/env";
import { reverseGeocodeAreaBbox, type SearchBbox } from "@/lib/geocode";
import type { Location, Coordinates } from "@fe-el-seka/shared";

const RideMap = dynamic(
  () => import("@/components/rides/RideMap").then((m) => ({ default: m.RideMap })),
  { ssr: false, loading: () => <div className="fixed inset-0 bg-surface-bg" /> }
);

type Phase = "form" | "results";

function toSearchLocation(loc?: Location, bbox?: SearchBbox | null): SearchLocation | undefined {
  if (!loc) return undefined;
  return { lat: loc.coordinates.lat, lng: loc.coordinates.lng, address: loc.address, bbox };
}

export default function SearchPage() {
  const router = useRouter();
  const t = useTranslations("passenger.search");
  const [phase, setPhase] = useState<Phase>("form");
  const [candidates, setCandidates] = useState<RideCandidate[]>([]);
  const [searchMeta, setSearchMeta] = useState<{
    origin: SearchLocation;
    destination: SearchLocation;
    departure_at: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sheetOpen, setSheetOpen] = useState(true);
  const [origin, setOrigin] = useState<Location | undefined>();
  const [destination, setDestination] = useState<Location | undefined>();
  const [destinationBbox, setDestinationBbox] = useState<SearchBbox | null>(null);
  const [selecting, setSelecting] = useState<"origin" | "destination" | null>(null);

  const handlePinDrop = async (coords: Coordinates, address: string) => {
    const loc: Location = { coordinates: coords, address };
    if (selecting === "origin") {
      setOrigin(loc);
      setSelecting("destination"); // Auto-advance to destination
    } else if (selecting === "destination") {
      setDestination(loc);
      setSelecting(null);
      setSheetOpen(true); // Reopen form after destination is placed
      // Widens dropoff matching to "driver ends anywhere in this area", not just
      // a tight walk radius around the exact pin — mirrors what typing a district
      // name used to give before Search became map-driven.
      const bbox = await reverseGeocodeAreaBbox(coords.lat, coords.lng);
      setDestinationBbox(bbox);
    }
  };

  const handleRequestOriginMap = () => {
    setSheetOpen(false);
    setSelecting("origin");
  };

  const handleRequestDestinationMap = () => {
    setSheetOpen(false);
    setSelecting("destination");
    setDestinationBbox(null);
  };

  const handleBackToForm = () => {
    setSheetOpen(true);
    setSelecting(null);
  };

  const handleSearch = async (
    searchOrigin: SearchLocation,
    searchDestination: SearchLocation,
    departureAt: string,
  ) => {
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/login"); return; }

      const res = await fetch(`${env.apiUrl}/api/v1/search/rides`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          origin: { lat: searchOrigin.lat, lng: searchOrigin.lng },
          destination: { lat: searchDestination.lat, lng: searchDestination.lng },
          dest_bbox: searchDestination.bbox ?? null,
          desired_departure_at: departureAt,
        }),
      });

      const json = await res.json();

      if (!res.ok) {
        if (res.status === 503) {
          setError(t("errors.routeServiceUnavailable"));
        } else {
          setError(json.message ?? t("errors.generic"));
        }
        return;
      }

      setCandidates(json.candidates ?? []);
      setSearchMeta({ origin: searchOrigin, destination: searchDestination, departure_at: departureAt });
      setPhase("results");
      setSheetOpen(true);
    } catch {
      setError(t("errors.network"));
    } finally {
      setLoading(false);
    }
  };

  const handleCardClick = (candidate: RideCandidate) => {
    if (!searchMeta) return;
    const params = new URLSearchParams({
      origin_lat: String(searchMeta.origin.lat),
      origin_lng: String(searchMeta.origin.lng),
      dest_lat: String(searchMeta.destination.lat),
      dest_lng: String(searchMeta.destination.lng),
      departure_at: searchMeta.departure_at,
    });
    router.push(`/rides/${candidate.ride_id}?${params}`);
  };

  const handleNewSearch = () => {
    setPhase("form");
    setError(null);
    setSheetOpen(true);
  };

  return (
    <>
      {/* Full-screen Leaflet map — always rendered behind the BottomSheet */}
      <div className="fixed inset-0 z-20">
        <RideMap onPinDrop={handlePinDrop} fullScreen />
      </div>

      {/* Overlay — always visible when sheet is closed so the user can always return */}
      {!sheetOpen && (
        <div className="fixed top-4 left-4 right-4 z-30 bg-surface-card border border-border-default rounded-xl px-4 py-3 space-y-1.5 shadow-sm">
          {selecting ? (
            <>
              <p className="text-label text-content-primary">
                {selecting === "origin" ? t("tapMapToSetOrigin") : t("tapMapToSetDestination")}
              </p>
              {origin && selecting === "destination" && (
                <p className="text-caption text-content-muted truncate">{t("originPrefix")} {origin.address}</p>
              )}
            </>
          ) : (
            <p className="text-label text-content-primary">{t("tapMapToExplore")}</p>
          )}
          <button type="button" onClick={handleBackToForm} className="text-body-sm text-brand-primary">
            {t("backToForm")}
          </button>
        </div>
      )}

      {/* BottomSheet containing the search form / results */}
      <BottomSheet isOpen={sheetOpen} onClose={() => setSheetOpen(false)} maxHeightPercent={80}>
        {phase === "form" || loading ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => router.push("/dashboard")}
                className="text-dash-navy hover:opacity-70"
              >
                <span className="inline-block rtl:rotate-180">←</span>
              </button>
              <div>
                <h1 className="text-h3 font-bold text-dash-navy">{t("heading")}</h1>
                <p className="text-sm text-dash-text-muted mt-1">{t("subheading")}</p>
              </div>
            </div>

            <RideSearchForm
              loading={loading}
              onSearch={handleSearch}
              externalOrigin={toSearchLocation(origin)}
              externalDestination={toSearchLocation(destination, destinationBbox)}
              onRequestOriginMap={handleRequestOriginMap}
              onRequestDestinationMap={handleRequestDestinationMap}
            />
            {error && <p className="text-sm text-content-destructive">{error}</p>}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => router.push("/dashboard")}
                className="text-dash-navy hover:opacity-70"
              >
                <span className="inline-block rtl:rotate-180">←</span>
              </button>
              <div className="flex-1 flex items-center justify-between">
                <p className="text-sm text-dash-text-muted">
                  {t("ridesFound", { count: candidates.length })}
                </p>
                <button
                  type="button"
                  onClick={handleNewSearch}
                  className="text-sm text-dash-primary font-semibold"
                >
                  {t("newSearch")}
                </button>
              </div>
            </div>

            {candidates.length === 0 ? (
              <div className="py-12 text-center space-y-2">
                <p className="text-dash-navy font-medium">{t("noRidesFoundTitle")}</p>
                <p className="text-sm text-dash-text-muted">
                  {t("noRidesFoundBody")}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {candidates.map((c) => (
                  <RideCard key={c.ride_id} candidate={c} onClick={handleCardClick} />
                ))}
              </div>
            )}
          </div>
        )}
      </BottomSheet>
    </>
  );
}
