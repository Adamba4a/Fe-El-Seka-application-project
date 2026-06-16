"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { OtpInput } from "@/components/auth/OtpInput";
import { verifyOtp, requestOtp } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/client";

export default function OtpPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [expiresAt] = useState(() => new Date(Date.now() + 5 * 60 * 1000));

  useEffect(() => {
    const e = sessionStorage.getItem("otp_email");
    if (!e) router.replace("/login");
    else setEmail(e);
  }, [router]);

  const handleComplete = async (otp: string) => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const session = await verifyOtp(email, otp);
      const supabase = createClient();
      await supabase.auth.setSession({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
      });
      sessionStorage.removeItem("otp_email");
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
      await requestOtp(email);
    } catch {
      setError("Could not resend code. Please wait before trying again.");
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Check your email</h1>
          <p className="text-gray-500 text-sm mt-1">
            We sent a 6-digit code to <strong>{email}</strong>
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
