"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PhoneInput } from "@/components/auth/PhoneInput";
import { requestOtp } from "@/lib/api/auth";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone.match(/^\+20\d{10}$/)) {
      setError("Enter a valid Egyptian phone number");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await requestOtp(phone);
      sessionStorage.setItem("otp_phone", phone);
      router.push("/otp");
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string };
      if (e?.error === "otp_rate_limited") {
        setError("Too many requests. Please wait 15 minutes before trying again.");
      } else {
        setError(e?.message ?? "Failed to send OTP. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Sign in to Fe El Seka</h1>
          <p className="text-gray-500 text-sm mt-1">Enter your Egyptian mobile number</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <PhoneInput value={phone} onChange={setPhone} error={error} disabled={loading} />
          <button
            type="submit"
            disabled={loading || !phone}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md font-medium disabled:opacity-50"
          >
            {loading ? "Sending…" : "Send OTP"}
          </button>
        </form>
      </div>
    </main>
  );
}
