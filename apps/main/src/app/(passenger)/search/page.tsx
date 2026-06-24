"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Spinner } from "@/components/ui/Spinner";
import { RideSearchForm, type SearchLocation } from "@/components/bookings/RideSearchForm";
import { RideCard, type RideCandidate } from "@/components/bookings/RideCard";
import { env } from "@/lib/env";

type Phase = "form" | "results";

export default function SearchPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("form");
  const [candidates, setCandidates] = useState<RideCandidate[]>([]);
  const [searchMeta, setSearchMeta] = useState<{
    origin: SearchLocation;
    destination: SearchLocation;
    departure: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (
    origin: SearchLocation,
    destination: SearchLocation,
    departure: string
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
          origin: { lat: origin.lat, lng: origin.lng },
          destination: { lat: destination.lat, lng: destination.lng },
          desired_departure_at: departure,
        }),
      });

      const json = await res.json();

      if (!res.ok) {
        if (res.status === 503) {
          setError("Route service unavailable — please try again shortly.");
        } else {
          setError(json.message ?? "Something went wrong.");
        }
        return;
      }

      setCandidates(json.candidates ?? []);
      setSearchMeta({ origin, destination, departure });
      setPhase("results");
    } catch {
      setError("Network error — please check your connection and try again.");
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
    });
    router.push(`/rides/${candidate.ride_id}?${params}`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-content-primary">Find a Ride</h1>
        <p className="text-sm text-content-muted mt-1">Search for rides along your route.</p>
      </div>

      {phase === "form" || loading ? (
        <div className="space-y-6">
          <RideSearchForm loading={loading} onSearch={handleSearch} />
          {error && <p className="text-sm text-content-destructive">{error}</p>}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-content-muted">
              {candidates.length} ride{candidates.length !== 1 ? "s" : ""} found
            </p>
            <button
              type="button"
              onClick={() => { setPhase("form"); setError(null); }}
              className="text-sm text-brand-primary font-medium"
            >
              New search
            </button>
          </div>

          {candidates.length === 0 ? (
            <div className="py-12 text-center space-y-2">
              <p className="text-content-primary font-medium">No rides found</p>
              <p className="text-sm text-content-muted">
                No rides match your route and time. Try adjusting your departure time.
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
    </div>
  );
}
