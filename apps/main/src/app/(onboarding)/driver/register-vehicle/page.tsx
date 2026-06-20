"use client";

import { useState } from "react";
import { VehicleRegistrationForm } from "@/components/vehicle/VehicleRegistrationForm";
import { registerVehicle } from "@/lib/api/vehicles";
import { createClient } from "@/lib/supabase/client";

export default function RegisterVehiclePage() {
  const [registered, setRegistered] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (data: Parameters<typeof registerVehicle>[1]) => {
    setError("");
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return;
    try {
      await registerVehicle(session.access_token, data);
      setRegistered(true);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Registration failed. Please try again.");
    }
  };

  if (registered) return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm text-center space-y-4">
        <p className="text-4xl">🎉</p>
        <h1 className="text-h2 text-content-primary">Ready to post rides!</h1>
        <p className="text-body-sm text-content-muted">Your vehicle has been registered. You can now create ride listings.</p>
        <a
          href="/rides/new"
          className="block w-full py-3 px-4 bg-brand-primary hover:bg-brand-primary-hover text-content-inverse text-body-sm font-medium rounded-xl text-center transition-colors"
        >
          Post Your First Ride
        </a>
        <a href="/rides" className="block text-body-sm text-content-muted hover:text-content-secondary">
          Go to My Rides
        </a>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-h3 text-content-primary">Register Your Vehicle</h1>
          <p className="text-body-sm text-content-muted mt-1">You need one vehicle to post rides</p>
        </div>
        {error && <p className="text-caption text-content-destructive">{error}</p>}
        <VehicleRegistrationForm onSubmit={handleSubmit} />
      </div>
    </main>
  );
}
