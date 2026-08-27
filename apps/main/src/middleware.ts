import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { resolveOrigin } from "@/lib/request-origin";
import {
  SESSION_MAX_AGE_MS,
  SESSION_STARTED_COOKIE,
  SESSION_STARTED_COOKIE_MAX_AGE_SECONDS,
} from "@/lib/auth/session-age";
import { defaultLocale, isLocale, localeCookieName } from "@/lib/i18n/config";

const PUBLIC_PATHS = ["/login", "/otp", "/signout", "/auth"];
// /signout must work even when a user IS authenticated (it clears a bad session).
// Do NOT redirect authenticated users away from it.
const ALLOW_AUTHENTICATED = ["/signout"];

const MAINTENANCE_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Triplyy — Temporarily Offline</title>
<style>
  body { margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:#0f172a; color:#f8fafc; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  main { max-width:28rem; padding:2rem; text-align:center; }
  h1 { font-size:1.5rem; margin-bottom:0.75rem; }
  p { color:#cbd5e1; line-height:1.5; }
</style>
</head>
<body>
<main>
  <h1>Triplyy is temporarily offline</h1>
  <p>We're performing required maintenance and will be back shortly. Thanks for your patience.</p>
</main>
</body>
</html>`;

export async function middleware(request: NextRequest) {
  if (process.env.MAINTENANCE_MODE === "true") {
    return new NextResponse(MAINTENANCE_HTML, {
      status: 503,
      headers: { "content-type": "text/html; charset=utf-8", "retry-after": "3600" },
    });
  }

  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  const origin = resolveOrigin(request);

  // Must use NextResponse.next({ request }) and reassign on cookie writes —
  // this is required for Supabase SSR to refresh the session cookie properly.
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.SUPABASE_INTERNAL_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookieOptions: { name: "sb-fe-el-seka-auth" },
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Use getUser() — not getSession() — so the JWT is validated with the
  // Supabase server and the session cookie is refreshed when needed.
  // This must stay directly after createServerClient with no logic in between.
  const { data: { user } } = await supabase.auth.getUser();

  // Enforce a 24h absolute session cap. Supabase's refresh-token rotation has
  // no built-in max lifetime (it's a sliding 60-day window), so without this
  // an active user is effectively signed in forever.
  if (user) {
    const startedAtRaw = request.cookies.get(SESSION_STARTED_COOKIE)?.value;
    const startedAt = startedAtRaw ? Number(startedAtRaw) : NaN;

    if (Number.isFinite(startedAt) && Date.now() - startedAt > SESSION_MAX_AGE_MS) {
      await supabase.auth.signOut();
      const redirectResponse = NextResponse.redirect(new URL("/login", origin));
      supabaseResponse.cookies.getAll().forEach((cookie) => redirectResponse.cookies.set(cookie));
      redirectResponse.cookies.delete(SESSION_STARTED_COOKIE);
      return redirectResponse;
    }

    if (!Number.isFinite(startedAt)) {
      // First request we've seen this session (fresh login, or an existing
      // session from before this cap existed) — start the 24h clock now.
      supabaseResponse.cookies.set(SESSION_STARTED_COOKIE, String(Date.now()), {
        path: "/",
        maxAge: SESSION_STARTED_COOKIE_MAX_AGE_SECONDS,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
      });
    }
  }

  if (!user && !isPublic) {
    return NextResponse.redirect(new URL("/login", origin));
  }

  const canPassThrough = ALLOW_AUTHENTICATED.some((p) => pathname.startsWith(p));
  if (user && isPublic && !canPassThrough) {
    return NextResponse.redirect(new URL("/", origin));
  }

  const cookieLocale = request.cookies.get(localeCookieName)?.value;
  let resolvedLocale = isLocale(cookieLocale) ? cookieLocale : defaultLocale;

  if (user) {
    const { data: profile } = await supabase
      .from("profiles")
      .select("language_preference")
      .eq("id", user.id)
      .single();

    if (profile && isLocale(profile.language_preference)) {
      resolvedLocale = profile.language_preference;
    }
  }

  if (resolvedLocale !== cookieLocale) {
    // Mutate `request.cookies` and rebuild `supabaseResponse` from it (same
    // pattern as the Supabase `setAll` callback above) so the NEXT_LOCALE
    // value is visible to the Server Components rendering *this* response,
    // not just to the browser on the *next* request. Rebuilding discards any
    // Set-Cookie headers already on the previous response instance (session
    // cookie, Supabase auth refresh cookies), so carry those over first.
    request.cookies.set(localeCookieName, resolvedLocale);
    const previousResponse = supabaseResponse;
    supabaseResponse = NextResponse.next({ request });
    previousResponse.cookies.getAll().forEach((cookie) => supabaseResponse.cookies.set(cookie));
    supabaseResponse.cookies.set(localeCookieName, resolvedLocale, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });
  }

  return supabaseResponse;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
