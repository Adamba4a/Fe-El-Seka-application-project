import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/otp", "/signout"];
// /signout must work even when a user IS authenticated (it clears a bad session).
// Do NOT redirect authenticated users away from it.
const ALLOW_AUTHENTICATED = ["/signout"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  // Must use NextResponse.next({ request }) and reassign on cookie writes —
  // this is required for Supabase SSR to refresh the session cookie properly.
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
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

  if (!user && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const canPassThrough = ALLOW_AUTHENTICATED.some((p) => pathname.startsWith(p));
  if (user && isPublic && !canPassThrough) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return supabaseResponse;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
