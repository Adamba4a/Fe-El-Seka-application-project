import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { env } from "@/lib/env";
import { resolveOrigin } from "@/lib/request-origin";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const next = request.nextUrl.searchParams.get("next");
  const origin = resolveOrigin(request);

  if (!code) {
    return NextResponse.redirect(new URL("/login?error=oauth_failed", origin));
  }

  let cookiesToApply: { name: string; value: string; options: Record<string, unknown> }[] = [];

  const supabase = createServerClient(
    process.env.SUPABASE_INTERNAL_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookieOptions: { name: "sb-fe-el-seka-auth" },
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (toSet) => {
          cookiesToApply = toSet;
        },
      },
    }
  );

  const { data, error } = await supabase.auth.exchangeCodeForSession(code);

  if (error || !data.session) {
    return NextResponse.redirect(new URL("/login?error=oauth_failed", origin));
  }

  // Password-recovery links carry an explicit `next` (e.g. /set-password) and
  // skip the OAuth-only new-vs-existing-user check below entirely.
  if (next) {
    const response = NextResponse.redirect(new URL(next, origin));
    cookiesToApply.forEach(({ name, value, options }) =>
      response.cookies.set(name, value, options)
    );
    return response;
  }

  let redirectPath = "/";
  try {
    const meRes = await fetch(`${env.serverApiUrl}/api/profiles/me`, {
      headers: { Authorization: `Bearer ${data.session.access_token}` },
    });
    if (meRes.status === 404) {
      redirectPath = "/role-select";
    } else if (meRes.ok) {
      const profile = await meRes.json();
      // Org-email access gate (Spec 025): checked after suspension (FR-012) —
      // a suspended account is left on the default "/" redirect so page.tsx's
      // existing suspension screen takes precedence over the gate.
      if (profile.verification_status !== "suspended" && !profile.org_verified_at) {
        redirectPath = "/verify-org-email";
      }
    }
  } catch {
    return NextResponse.redirect(new URL("/login?error=oauth_failed", origin));
  }

  const response = NextResponse.redirect(new URL(redirectPath, origin));
  cookiesToApply.forEach(({ name, value, options }) =>
    response.cookies.set(name, value, options)
  );
  return response;
}
