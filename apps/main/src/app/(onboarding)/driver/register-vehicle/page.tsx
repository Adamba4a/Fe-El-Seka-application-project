"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { VehicleRegistrationForm } from "@/components/vehicle/VehicleRegistrationForm";
import { registerVehicle } from "@/lib/api/vehicles";
import { createClient } from "@/lib/supabase/client";

export default function RegisterVehiclePage() {
  const t = useTranslations("onboarding.registerVehicle");
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
      setError(e?.message ?? t("errors.registrationFailed"));
    }
  };

  if (registered) return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm text-center space-y-4">
        <p className="text-4xl">🎉</p>
        <h1 className="text-h2 text-content-primary">{t("successTitle")}</h1>
        <p className="text-body-sm text-content-muted">{t("successBody")}</p>
        <a
          href="/rides/new"
          className="block w-full py-3 px-4 bg-dash-primary hover:opacity-90 text-content-inverse text-body-sm font-medium rounded-xl text-center transition-opacity"
        >
          {t("postFirstRide")}
        </a>
        <a href="/rides" className="block text-body-sm text-content-muted hover:text-content-secondary">
          {t("goToMyRides")}
        </a>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen flex items-center justify-center p-4 bg-surface-bg">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-h3 text-content-primary">{t("title")}</h1>
          <p className="text-body-sm text-content-muted mt-1">{t("subtitle")}</p>
        </div>
        {error && <p className="text-caption text-content-destructive">{error}</p>}
        <VehicleRegistrationForm onSubmit={handleSubmit} />
      </div>
    </main>
  );
}
