"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { requestOtp } from "@/lib/api/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.includes("@") || !email.includes(".")) {
      setError("Enter a valid email address");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await requestOtp(email);
      sessionStorage.setItem("otp_email", email);
      router.push("/otp");
    } catch (err: unknown) {
      const e = err as { error?: string; message?: string };
      if (e?.error === "otp_rate_limited") {
        setError("Too many requests. Please wait 15 minutes before trying again.");
      } else {
        setError(e?.message ?? "Failed to send code. Please try again.");
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
          <p className="text-gray-500 text-sm mt-1">Enter your email to receive a verification code</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium">Email address</label>
            <input
              type="email"
              inputMode="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
              className="px-3 py-2 border rounded-md text-sm outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              autoComplete="email"
            />
            {error && <p className="text-red-500 text-xs">{error}</p>}
          </div>
          <button
            type="submit"
            disabled={loading || !email}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md font-medium disabled:opacity-50"
          >
            {loading ? "Sending…" : "Send Code"}
          </button>
        </form>
      </div>
    </main>
  );
}
