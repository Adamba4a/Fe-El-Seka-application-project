import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { env } from "@/lib/env";
import { resolveOrigin } from "@/lib/request-origin";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
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

  let redirectPath = "/";
  try {
    const meRes = await fetch(`${env.serverApiUrl}/api/profiles/me`, {
      headers: { Authorization: `Bearer ${data.session.access_token}` },
    });
    if (meRes.status === 404) {
      redirectPath = "/role-select";
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
