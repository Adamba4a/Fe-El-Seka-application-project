"use client";

import { useEffect, useState } from "react";
import { createBrowserClient } from "@supabase/ssr";
import { OtpInput } from "@/components/auth/OtpInput";
import { verifyOtp, requestOtp } from "@/lib/api/auth";

export default function OtpPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [expiresAt] = useState(() => new Date(Date.now() + 5 * 60 * 1000));

  useEffect(() => {
    const e = sessionStorage.getItem("otp_email");
    if (!e) window.location.replace("/login");
    else setEmail(e);
  }, []);

  const handleComplete = async (otp: string) => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const session = await verifyOtp(email, otp);
      const redirectTo = session.user.is_new_user ? "/role-select" : "/";

      // Set the Supabase session in browser cookies so the middleware can
      // read it on the next navigation. The fixed cookieOptions.name keeps
      // this in sync with the server client used in middleware.ts.
      const supabase = createBrowserClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        { cookieOptions: { name: "sb-fe-el-seka-auth" } }
      );
      const { error: sessionError } = await supabase.auth.setSession({
        access_token: session.access_token,
        refresh_token: session.refresh_token,
      });

      if (sessionError) {
        setError(sessionError.message ?? "Could not establish session. Please try again.");
        return;
      }

      sessionStorage.removeItem("otp_email");
      window.location.replace(redirectTo);
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
