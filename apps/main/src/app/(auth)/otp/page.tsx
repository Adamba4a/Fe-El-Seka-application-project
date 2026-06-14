"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { OtpInput } from "@/components/auth/OtpInput";
import { verifyOtp, requestOtp } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";

export default function OtpPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [expiresAt] = useState(() => new Date(Date.now() + 5 * 60 * 1000));

  useEffect(() => {
    const p = sessionStorage.getItem("otp_phone");
    if (!p) router.replace("/login");
    else setPhone(p);
  }, [router]);

  const handleComplete = async (otp: string) => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const session = await verifyOtp(phone, otp);
      const supabase = createClient();
      await supabase.auth.setSession({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
      });
      sessionStorage.removeItem("otp_phone");
      if (session.user.is_new_user) {
        router.replace("/role-select");
      } else {
        router.replace("/");
      }
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string };
      if (e?.error === "otp_expired") {
        setError("Code has expired. Please request a new one.");
      } else {
        setError(e?.message ?? "Incorrect code. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      await requestOtp(phone);
    } catch {
      setError("Could not resend code. Please wait before trying again.");
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Enter your code</h1>
          <p className="text-gray-500 text-sm mt-1">
            We sent a 6-digit code to <strong>{phone}</strong>
          </p>
        </div>

        <OtpInput
          onComplete={handleComplete}
          disabled={loading}
          error={error}
          expiresAt={expiresAt}
          onResend={handleResend}
        />
      </div>
    </main>
  );
}
